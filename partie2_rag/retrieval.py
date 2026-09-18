"""Index vectoriel dense LSA et recherche hybride, sans réseau ni poids externes.

LSA = TF-IDF + TruncatedSVD ; ce ne sont PAS des embeddings neuronaux E5.
Le petit corpus est recherché exactement par produit scalaire normalisé NumPy.
BM25 est fusionné par rangs (RRF), jamais par addition de scores incompatibles.
"""
from __future__ import annotations
import hashlib
import json
import math
import re
from collections import Counter
from importlib.metadata import version
from pathlib import Path
import joblib
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import normalize
from partie2_rag.ingest import folded

STOPWORDS=set('le la les de des du un une et est en a au aux dans pour sur ce ces se que quelles quels quelle quel sont s l d t il elle on'.split())

def tokenize(text):
    return [t for t in re.findall(r'\w+',folded(text)) if t not in STOPWORDS]

def reciprocal_rank_fusion(rankings,constant=60):
    if constant<=0:raise ValueError('Constante RRF positive requise.')
    out={}
    for ranking in rankings:
        seen=set()
        for rank,item in enumerate(ranking,1):
            if item in seen:continue
            seen.add(item);out[item]=out.get(item,0.)+1./(constant+rank)
    return out

def write_json(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def build_index(chunks,index_dir: Path,dimension=64):
    if len(chunks)<3:raise ValueError('Au moins trois chunks sont nécessaires au petit index LSA.')
    if len({c['chunk_id'] for c in chunks})!=len(chunks):raise ValueError('Identifiants dupliqués.')
    index_dir=Path(index_dir);index_dir.mkdir(parents=True,exist_ok=True)
    texts=[f"{c['product']} {c['level']} {c['section']}\n{c['text']}" for c in chunks]
    vectorizer=TfidfVectorizer(tokenizer=tokenize,token_pattern=None,lowercase=False,ngram_range=(1,2),sublinear_tf=True)
    sparse=vectorizer.fit_transform(texts)
    dim=min(dimension,len(chunks)-1,sparse.shape[1]-1)
    if dim<1:raise ValueError('Vocabulaire insuffisant.')
    svd=TruncatedSVD(n_components=dim,n_iter=10,random_state=42)
    vectors=normalize(svd.fit_transform(sparse)).astype('float32')
    if not np.isfinite(vectors).all():raise ValueError('Embeddings non finis.')
    # Manifest écrit en dernier : toute modification partielle sera refusée au chargement.
    joblib.dump({'vectorizer':vectorizer,'svd':svd},index_dir/'encoder.joblib',compress=3)
    np.save(index_dir/'vectors.npy',vectors,allow_pickle=False)
    write_json(index_dir/'chunks.json',chunks)
    manifest={'format_version':1,'embedding':'TF-IDF(word 1-2 grams) + TruncatedSVD + L2 normalization',
        'neural_pretrained':False,'vector_store':'NumPy exact inner product of normalized vectors',
        'dimension':int(vectors.shape[1]),'n_chunks':len(chunks),'n_documents':len({c['document'] for c in chunks}),
        'sklearn_version':version('scikit-learn'),'seed':42,'chunking':{'unit':'whitespace words','maximum':240,'overlap':40},
        'fingerprints':{name:hashlib.sha256((index_dir/name).read_bytes()).hexdigest() for name in ['encoder.joblib','vectors.npy','chunks.json']},
        'source_fingerprints':{c['document']:c.get('source_sha256') for c in chunks}}
    write_json(index_dir/'manifest.json',manifest)
    return manifest

class Retriever:
    def __init__(self,index_dir: Path):
        folder=Path(index_dir);self.manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
        if self.manifest['sklearn_version']!=version('scikit-learn'):
            raise ValueError('Version sklearn différente : reconstruire l’index.')
        for name,expected in self.manifest['fingerprints'].items():
            if hashlib.sha256((folder/name).read_bytes()).hexdigest()!=expected:
                raise ValueError(f'Empreinte invalide : {name}. Reconstruire l’index.')
        self.chunks=json.loads((folder/'chunks.json').read_text(encoding='utf-8'))
        self.vectors=np.load(folder/'vectors.npy',allow_pickle=False)
        if self.vectors.shape!=(len(self.chunks),self.manifest['dimension']):raise ValueError('Dimensions incompatibles.')
        self.encoder=joblib.load(folder/'encoder.joblib')
        self.documents=[tokenize(f"{c['product']} {c['level']} {c['section']}\n{c['text']}") for c in self.chunks]
        self.tf=[Counter(d) for d in self.documents]
        self.lengths=np.array([len(d) for d in self.documents],dtype=float)
        self.average_length=float(self.lengths.mean())
        df=Counter(t for d in self.documents for t in set(d));n=len(self.chunks)
        self.idf={t:math.log(1+(n-f+.5)/(f+.5)) for t,f in df.items()}

    def bm25(self,question):
        result=np.zeros(len(self.chunks));k1=1.5;b=.75
        for token in set(tokenize(question)):
            if token not in self.idf:continue
            f=np.array([d.get(token,0) for d in self.tf])
            result+=self.idf[token]*f*(k1+1)/(f+k1*(1-b+b*self.lengths/self.average_length))
        return result

    @staticmethod
    def filters(question):
        words=set(tokenize(question))
        products={'auto':'Assurance Auto','habitation':'Assurance Habitation','sante':'Assurance Santé','vie':'Assurance Vie','pro':'Multirisque Pro'}
        matched={p for token,p in products.items() if token in words}
        levels={s.capitalize() for s in ['essentiel','confort','premium'] if s in words}
        # Ambiguïté/comparaison : ne pas filtrer arbitrairement un seul produit.
        return (next(iter(matched)) if len(matched)==1 else None,next(iter(levels)) if len(levels)==1 else None)

    def search(self,question,top_k=5,mode='dense',candidates=20):
        if mode not in {'dense','hybrid','hybrid_filtered'} or not 1<=top_k<=50:
            raise ValueError('Mode invalide ou top_k hors 1..50.')
        if not isinstance(question,str) or not question.strip() or len(question)>5000:
            raise ValueError('Question vide ou trop longue.')
        lexical=self.bm25(question)
        if lexical.max(initial=0)<=0:return []
        sparse=self.encoder['vectorizer'].transform([question])
        vector=normalize(self.encoder['svd'].transform(sparse)).astype('float32')[0]
        dense=self.vectors@vector
        eligible=list(range(len(self.chunks)))
        if mode=='hybrid_filtered':
            product,level=self.filters(question)
            eligible=[i for i,c in enumerate(self.chunks) if (product is None or c['product']==product) and (level is None or c['level'] in {level,'FAQ'})]
        dr=sorted(eligible,key=lambda i:(-float(dense[i]),self.chunks[i]['chunk_id']))
        br=sorted((i for i in eligible if lexical[i]>0),key=lambda i:(-float(lexical[i]),self.chunks[i]['chunk_id']))
        fusion=reciprocal_rank_fusion([dr[:candidates],br[:candidates]]) if mode!='dense' else {}
        ranked=dr if mode=='dense' else sorted(fusion,key=lambda i:(-fusion[i],self.chunks[i]['chunk_id']))
        dranks={j:i+1 for i,j in enumerate(dr)};branks={j:i+1 for i,j in enumerate(br)}
        result=[]
        for rank,i in enumerate(ranked[:top_k],1):
            result.append({**self.chunks[i],'rank':rank,'similarity_cosine':float(dense[i]),
                'bm25_score':float(lexical[i]),'rrf_score':float(fusion[i]) if i in fusion else None,
                'dense_rank':dranks.get(i),'bm25_rank':branks.get(i),'retrieval_mode':mode})
        return result
