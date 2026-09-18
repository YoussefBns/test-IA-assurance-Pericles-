"""Validation et intégration avec le véritable artefact livré."""
import importlib.util
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[2]

def test_api_module_exists():
    assert importlib.util.find_spec('partie3_mlops.app') is not None

@pytest.fixture
def payload():
    return json.loads((ROOT/'partie3_mlops/example_request.json').read_text())

@pytest.fixture
def client(tmp_path):
    from partie3_mlops.app import create_app
    app=create_app(log_dir=tmp_path)
    with TestClient(app) as c:
        yield c

@pytest.mark.integration
def test_health_and_predict(client,payload):
    health=client.get('/health');assert health.status_code==200
    assert health.json()['model_version']
    r=client.post('/predict',json=payload);assert r.status_code==200
    b=r.json();assert set(b)=={'client_id','churn_probability','prediction','risk_level'}
    assert 0<=b['churn_probability']<=1
    assert type(b['prediction']) is int
    assert b['risk_level'] in ['faible','modéré','élevé']

@pytest.mark.parametrize('field,value',[
    ('age','45'),('age',True),('nb_sinistres_12m',1.5),('prime_mensuelle_eur','cent'),
    ('prime_mensuelle_eur',-1),('prime_mensuelle_eur',True),('score_satisfaction',6),
    ('resiliation_anterieure',True),('resiliation_anterieure',2),
    ('date_souscription','2024-02-31'),('profession','')])
def test_invalid_input_422(client,payload,field,value):
    payload[field]=value
    assert client.post('/predict',json=payload).status_code==422

@pytest.mark.parametrize('field',['age','prime_mensuelle_eur','client_id'])
def test_missing_required(client,payload,field):
    payload.pop(field)
    assert client.post('/predict',json=payload).status_code==422

@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity'])
def test_non_finite_json_rejected_without_server_error(client,payload,value):
    text=json.dumps(payload).replace('95.0',value)
    assert client.post('/predict',content=text,headers={'Content-Type':'application/json'}).status_code==422

@pytest.mark.parametrize('field',['churned','unexpected'])
def test_extra_forbidden(client,payload,field):
    payload[field]=1
    assert client.post('/predict',json=payload).status_code==422

def test_nulls_and_unknown_category(client,payload):
    payload.update(score_satisfaction=None,nb_appels_support_12m=None,profession='Nouvelle profession')
    assert client.post('/predict',json=payload).status_code==200

def test_optional_missing_allowed(client,payload):
    payload.pop('score_satisfaction');payload.pop('nb_appels_support_12m')
    assert client.post('/predict',json=payload).status_code==200

def test_chronological_error(client,payload):
    payload['date_derniere_interaction']='2020-01-01'
    assert client.post('/predict',json=payload).status_code==422

@pytest.mark.integration
def test_same_pipeline_probability(client,payload):
    model=joblib.load(ROOT/'partie1_ml/model.joblib')
    expected=model.predict_proba(pd.DataFrame([payload]))[0,1]
    actual=client.post('/predict',json=payload).json()['churn_probability']
    assert actual==pytest.approx(expected,abs=1e-12)

def test_missing_model_is_unhealthy(tmp_path,payload):
    from partie3_mlops.app import create_app
    with TestClient(create_app(model_path=tmp_path/'absent.joblib',log_dir=tmp_path/'logs')) as c:
        assert c.get('/health').status_code==503
        assert c.post('/predict',json=payload).status_code==503

def test_corrupt_model_is_unhealthy(tmp_path):
    from partie3_mlops.app import create_app
    bad=tmp_path/'model.joblib';bad.write_bytes(b'not a model')
    with TestClient(create_app(model_path=bad,log_dir=tmp_path/'logs')) as c:
        assert c.get('/health').status_code==503

def test_risk_boundaries():
    from partie3_mlops.app import risk_level
    assert risk_level(.249,.25,.5)=='faible'
    assert risk_level(.25,.25,.5)=='modéré'
    assert risk_level(.499,.25,.5)=='modéré'
    assert risk_level(.5,.25,.5)=='élevé'

def test_prediction_log_is_jsonl_and_minimizes_identifier(tmp_path,payload):
    from partie3_mlops.app import create_app
    with TestClient(create_app(log_dir=tmp_path)) as c:
        assert c.post('/predict',json=payload).status_code==200
    rows=[json.loads(s) for s in (tmp_path/'predictions.jsonl').read_text().splitlines()]
    assert len(rows)==1
    r=rows[0];assert r['model_version'] and r['request_id'] and r['timestamp_utc']
    assert r['duration_ms']>=0 and r['inputs']['montant_sinistres_eur']==1500
    assert 'client_id' not in r['inputs'] and 'client_id' not in r['output']
