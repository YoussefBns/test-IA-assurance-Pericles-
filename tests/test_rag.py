"""Tests RAG hors réseau ; aucune réponse métier codée en dur dans le moteur."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_rag_modules_exist():
    assert importlib.util.find_spec('partie2_rag.ingest') is not None
    assert importlib.util.find_spec('partie2_rag.retrieval') is not None

@pytest.fixture
def chunks():
    return [
      {'chunk_id':'a','document':'auto.pdf','pages':[1],'product':'Assurance Auto','level':'Premium','section':'Garanties','text':'Bris de glace auto premium franchise zéro euros.'},
      {'chunk_id':'b','document':'sante.pdf','pages':[2],'product':'Assurance Santé','level':'Essentiel','section':'Conditions','text':'Santé essentiel carence trois mois pour hospitalisation.'},
      {'chunk_id':'c','document':'vie.pdf','pages':[1],'product':'Assurance Vie','level':'FAQ','section':'Exclusions','text':'Assurance vie exclusions compétition sportive parachutisme.'},
      {'chunk_id':'d','document':'auto-faq.pdf','pages':[1],'product':'Assurance Auto','level':'FAQ','section':'Franchise','text':'Assurance auto bris de glace formule Premium sans franchise.'}]

def test_tokenizer_preserves_negation_and_numbers():
    from partie2_rag.retrieval import tokenize
    tokens=tokenize('Aucune franchise de 150 € ; sans exclusion, pas de délai.')
    assert {'aucune','150','sans','pas','exclusion','delai'} <= set(tokens)

def test_rrf_has_no_duplicate_and_is_deterministic():
    from partie2_rag.retrieval import reciprocal_rank_fusion
    a=reciprocal_rank_fusion([[1,2,3],[2,1,4]])
    assert len(a)==4 and a==reciprocal_rank_fusion([[1,2,3],[2,1,4]])
    assert a[1]==pytest.approx(1/61+1/62)

def test_index_reload_and_empty_query(tmp_path,chunks):
    from partie2_rag.retrieval import build_index,Retriever
    build_index(chunks,tmp_path)
    a=Retriever(tmp_path);b=Retriever(tmp_path)
    q='franchise bris de glace Auto Premium'
    assert a.search(q)==b.search(q)
    assert a.search('zzzzxywnotincorpus')==[]
    assert np.allclose(np.linalg.norm(a.vectors,axis=1),1,atol=1e-5)

def test_index_detects_tampering(tmp_path,chunks):
    from partie2_rag.retrieval import build_index,Retriever
    build_index(chunks,tmp_path)
    (tmp_path/'chunks.json').write_text('[]')
    with pytest.raises(ValueError,match='Empreinte'):
        Retriever(tmp_path)

def test_filter_keeps_faq_and_requested_product(tmp_path,chunks):
    from partie2_rag.retrieval import build_index,Retriever
    build_index(chunks,tmp_path)
    got=Retriever(tmp_path).search('Franchise Auto Premium bris de glace',mode='hybrid_filtered')
    assert got and all(c['product']=='Assurance Auto' for c in got)
    assert set(c['level'] for c in got)<={'Premium','FAQ'}

def test_bad_top_k_and_mode(tmp_path,chunks):
    from partie2_rag.retrieval import build_index,Retriever
    build_index(chunks,tmp_path);r=Retriever(tmp_path)
    with pytest.raises(ValueError):r.search('auto',top_k=0)
    with pytest.raises(ValueError):r.search('auto',mode='invalid')

def test_context_metric_definitions():
    from partie2_rag.evaluation import relevance_metrics
    m=relevance_metrics(['a','b','c'],{'a','c','d'})
    assert m['context_precision']==pytest.approx(2/3)
    assert m['ranked_context_precision']==pytest.approx((1+2/3)/2)
    assert m['evidence_recall']==pytest.approx(2/3)
    assert relevance_metrics([],{'a'})['context_precision'] is None

def test_prompt_citations_and_no_context(chunks):
    from partie2_rag.generation import build_messages,citation_audit
    messages=build_messages('Quelle franchise ?',chunks[:1])
    assert 'exclusivement' in messages[0]['content']
    assert '[a]' in messages[1]['content'] and 'auto.pdf' in messages[1]['content']
    assert citation_audit('Franchise zéro [a].',chunks[:1])['valid_ids']==['a']
    assert citation_audit('Réponse [invented].',chunks[:1])['invalid_ids']==['invented']
    assert 'AUCUN PASSAGE' in build_messages('Question',[])[1]['content']

@pytest.mark.integration
def test_real_corpus_integrity_and_cross_page_faq():
    from partie2_rag.ingest import extract_corpus
    a=extract_corpus(ROOT/'data/fiches_produits')
    b=extract_corpus(ROOT/'data/fiches_produits')
    assert a==b
    assert len({c['document'] for c in a})==20
    assert len({c['chunk_id'] for c in a})==len(a)
    assert all(c['word_count']<=240 and c['pages'] for c in a)
    pro=[c for c in a if c['document']=='fiche_pro_faq.pdf' and 'resilier' in c['section'].lower()]
    assert pro and pro[0]['pages']==[1,2]
    assert 'premiere' in pro[0]['text'].lower()
