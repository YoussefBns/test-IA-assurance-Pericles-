"""Intégrité des artefacts réellement entraînés et cohérence de la livraison."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]


def test_model_metadata_hash_and_holdout_reproduction():
    metadata = json.loads((ROOT / 'partie1_ml/metadata.json').read_text())
    model_path = ROOT / 'partie1_ml/model.joblib'
    assert hashlib.sha256(model_path.read_bytes()).hexdigest() == metadata['model_sha256']
    df = pd.read_csv(ROOT / 'data/dataset_assurance_churn.csv')
    split = json.loads((ROOT / 'partie1_ml/outputs/split_manifest.json').read_text())
    train_ids, test_ids = set(split['train_client_ids']), set(split['test_client_ids'])
    assert train_ids.isdisjoint(test_ids)
    assert train_ids | test_ids == set(df.client_id)
    assert (len(train_ids), len(test_ids)) == (1600, 400)
    test = df.set_index('client_id').loc[split['test_client_ids']].reset_index()
    model = joblib.load(model_path)
    p = model.predict_proba(test.drop(columns='churned'))[:, 1]
    assert roc_auc_score(test.churned, p) == pytest.approx(metadata['metrics']['auc_roc'])
    assert average_precision_score(test.churned, p) == pytest.approx(metadata['metrics']['average_precision'])
    saved = pd.read_csv(ROOT / 'partie1_ml/outputs/predictions_logistic_regression.csv')
    assert saved.client_id.tolist() == test.client_id.tolist()
    np.testing.assert_allclose(p, saved.probability, atol=1e-12, rtol=0)


def test_imputation_statistics_come_from_train_only():
    model = joblib.load(ROOT / 'partie1_ml/model.joblib')
    df = pd.read_csv(ROOT / 'data/dataset_assurance_churn.csv')
    split = json.loads((ROOT / 'partie1_ml/outputs/split_manifest.json').read_text())
    train = df.set_index('client_id').loc[split['train_client_ids']].reset_index().drop(columns='churned')
    features = model.named_steps['features'].transform(train)
    from partie1_ml.features import NUMERIC
    actual = model.named_steps['preprocessor'].named_transformers_['num'].named_steps['imputer'].statistics_
    np.testing.assert_allclose(actual, features[NUMERIC].median().to_numpy(), rtol=0, atol=0)


def test_monitoring_reference_matches_train_histograms():
    from partie3_mlops.monitoring import histogram, psi
    df = pd.read_csv(ROOT / 'data/dataset_assurance_churn.csv')
    split = json.loads((ROOT / 'partie1_ml/outputs/split_manifest.json').read_text())
    train = df[df.client_id.isin(split['train_client_ids'])]
    reference = json.loads((ROOT / 'partie1_ml/drift_reference.json').read_text())
    for column, info in reference.items():
        counts = histogram(train[column], info['finite_edges'])
        assert counts == info['counts']
        assert psi(info['counts'], counts) == 0


def test_benchmark_prompt_hashes_and_answers_are_honest():
    from partie2_rag.generation import prompt_hash, citation_audit
    result = json.loads((ROOT / 'partie2_rag/results.json').read_text())
    assert len(result['runs']) == 15
    assert result['batch_import']['live_api_verified'] is False
    for row in result['runs']:
        assert prompt_hash(row['messages']) == row['prompt_sha256']
        assert row['generation']['execution'] == 'chatgpt_interactive_batch'
        assert not citation_audit(row['answer'], row['chunks'])['invalid_ids']


def test_dockerfiles_match_and_package_artifact():
    content = (ROOT / 'Dockerfile').read_text()
    assert content == (ROOT / 'partie3_mlops/Dockerfile').read_text()
    assert 'model.joblib' in content and 'USER app' in content
    assert 'requirements-api.txt' in content
    assert 'partie2_rag' not in content
    assert 'model.joblib' not in (ROOT / '.dockerignore').read_text()


def test_all_json_outputs_are_standard_json():
    def reject(value):
        raise ValueError('JSON non fini : ' + value)
    for path in ROOT.rglob('*.json'):
        json.loads(path.read_text(encoding='utf-8'), parse_constant=reject)
