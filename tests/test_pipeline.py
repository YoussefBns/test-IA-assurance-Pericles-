"""Tests du protocole de benchmark, sans service LLM payant."""
from pathlib import Path
import importlib.util
import json
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_pipeline_module_exists():
    assert importlib.util.find_spec('partie2_rag.pipeline') is not None

def test_gold_evidence_is_real_and_complete():
    from partie2_rag.pipeline import load_annotations
    from partie2_rag.retrieval import Retriever
    gold=load_annotations(ROOT/'partie2_rag/annotations.json',Retriever(ROOT/'partie2_rag/index').chunks)
    assert set(gold)=={'Q1','Q2','Q3','Q4','Q5'}
    assert all(len(v)>0 for v in gold.values())

def test_missing_generation_remains_missing(tmp_path):
    from partie2_rag.pipeline import benchmark
    result=benchmark(ROOT/'partie2_rag/index',ROOT/'partie2_rag/questions.json',ROOT/'partie2_rag/annotations.json',generation='none')
    assert len(result['runs'])==15
    for row in result['runs']:
        assert row['answer'] is None
        assert row['generation']['status']=='not_run'
        assert row['metrics']['context_precision'] is not None
        assert len(row['prompt_sha256'])==64
        assert row['messages'][-1]['content'].endswith(row['question'])
    json.dumps(result,allow_nan=False)

def test_reference_answers_cannot_be_imported_as_live_generation():
    from partie2_rag.pipeline import attach_batch_answers,benchmark
    result=benchmark(ROOT/'partie2_rag/index',ROOT/'partie2_rag/questions.json',ROOT/'partie2_rag/annotations.json',generation='none')
    with pytest.raises(ValueError,match='prompt'):
        attach_batch_answers(result,{'execution':'chatgpt_interactive_batch','responses':[{'question_id':'Q1','mode':'dense','prompt_sha256':'wrong','answer':'test'}]})


def test_ingestion_cli_rejects_incomplete_subject_corpus(tmp_path):
    from partie2_rag.pipeline import main
    from shutil import copy2
    copy2(ROOT/'data/fiches_produits/fiche_auto_premium.pdf',tmp_path/'fiche_auto_premium.pdf')
    assert main(['ingest','--pdf-dir',str(tmp_path),'--index',str(tmp_path/'index')]) == 2
