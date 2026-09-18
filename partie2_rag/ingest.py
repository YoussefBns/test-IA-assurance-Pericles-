"""Extraction native des PDF : sections, tables linéarisées, provenance par page.

Les 20 PDF fournis ont une couche texte. Les retours à la ligne des tableaux
sont préservés. Les pages à mauvaise extraction font échouer l'ingestion.
"""
from __future__ import annotations
import hashlib
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader

PRODUCTS={'auto':'Assurance Auto','habitation':'Assurance Habitation','sante':'Assurance Santé','vie':'Assurance Vie','pro':'Multirisque Pro'}
HEADINGS={'tableau des garanties','principales exclusions','conditions de souscription','tarification indicative'}

def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))

def metadata(path,text):
    bits=path.stem.split('_')
    if len(bits)!=3 or bits[1] not in PRODUCTS or bits[2] not in {'essentiel','confort','premium','faq'}:
        raise ValueError(f'Nom de fiche non reconnu : {path.name}')
    product=PRODUCTS[bits[1]];level=bits[2].upper() if bits[2]=='faq' else bits[2].capitalize()
    if folded(product) not in folded(text) or folded(level) not in folded(text):
        raise ValueError(f'Métadonnées non confirmées dans la fiche : {path.name}')
    return product,level

def clean_lines(text,product,level):
    skip={folded(product),folded(level),'auto','hab','sante','vie','pro','faq'}
    for line in text.replace('\x7f','•').splitlines():
        line=line.strip()
        if not line:continue
        if folded(line) in skip or re.fullmatch(r'Page\s+\d+',line):continue
        if line.startswith('Fiche produit officielle') or line.startswith('AssurCo S.A.'):continue
        if line.startswith('Document non contractuel'):break
        yield line

def extract_corpus(pdf_dir: Path,max_words=240,overlap=40):
    if not 0<=overlap<max_words:raise ValueError('Overlap invalide.')
    files=sorted(Path(pdf_dir).glob('*.pdf'))
    if not files:raise FileNotFoundError(f'Aucun PDF dans {pdf_dir}')
    chunks=[]
    for path in files:
        reader=PdfReader(path)
        pages=[p.extract_text() or '' for p in reader.pages]
        if any(len(t.strip())<30 for t in pages):
            raise ValueError(f'Extraction insuffisante : {path.name}. Vérifier le PDF visuellement.')
        product,level=metadata(path,'\n'.join(pages))
        groups=[];title='Présentation';lines=[]
        for page_number,text in enumerate(pages,1):
            for line in clean_lines(text,product,level):
                if folded(line) in HEADINGS or line.startswith('Q.'):
                    if lines:groups.append((title,lines))
                    title=line;lines=[(line,page_number)]
                else:
                    lines.append((line,page_number))
        if lines:groups.append((title,lines))
        for si,(section,lines) in enumerate(groups):
            # Spans de tokens conservant les sauts de ligne et la page d'origine.
            text=''; spans=[]
            for line,page in lines:
                offset=len(text)
                for match in re.finditer(r'\S+',line):
                    spans.append((offset+match.start(),offset+match.end(),page))
                text+=line+'\n'
            if not spans:continue
            start=0;wi=0
            while start<len(spans):
                end=min(start+max_words,len(spans))
                snippet=text[spans[start][0]:spans[end-1][1]]
                pp=sorted({s[2] for s in spans[start:end]})
                chunks.append({'chunk_id':f'{path.stem}:s{si:02d}:w{wi:02d}',
                    'document':path.name,'pages':pp,'product':product,'level':level,
                    'section':section,'text':snippet,'word_count':end-start,
                    'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'text_sha256':hashlib.sha256(snippet.encode()).hexdigest()})
                if end==len(spans):break
                start=end-overlap;wi+=1
    return chunks
