"""API de démonstration déployable, sans entraînement au démarrage.

Un seul worker par processus de logs. Authentification, TLS, rétention des logs
et validation métier restent nécessaires avant exposition en production.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from logging.handlers import RotatingFileHandler
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from partie3_mlops.schemas import PredictionInput, PredictionOutput

ROOT=Path(__file__).resolve().parents[1]


def risk_level(probability: float, moderate: float, high: float) -> str:
    if probability >= high: return 'élevé'
    if probability >= moderate: return 'modéré'
    return 'faible'


def create_app(model_path: Path | None = None, log_dir: Path | None = None) -> FastAPI:
    artifact=Path(model_path or os.getenv('CHURN_MODEL_PATH',str(ROOT/'partie1_ml/model.joblib')))
    log_root=Path(log_dir or os.getenv('CHURN_LOG_DIR',str(ROOT/'logs')))

    @asynccontextmanager
    async def lifespan(app):
        app.state.ready=False
        app.state.model_version=None
        app.state.handler=None
        try:
            metadata=json.loads(artifact.with_name('metadata.json').read_text(encoding='utf-8'))
            if hashlib.sha256(artifact.read_bytes()).hexdigest()!=metadata['model_sha256']:
                raise ValueError('Empreinte du modèle invalide.')
            if metadata['packages']['scikit-learn']!=version('scikit-learn'):
                raise ValueError('Version scikit-learn incompatible avec l’artefact.')
            threshold=float(metadata['threshold'])
            moderate=float(metadata['risk_bounds']['moderate']);high=float(metadata['risk_bounds']['high'])
            if not 0<moderate<high<1 or threshold!=high:
                raise ValueError('Politique de seuils incohérente.')
            # L'artefact est local et de confiance ; aucun chargement utilisateur.
            model=joblib.load(artifact)
            if list(model.classes_) != [0,1]:
                raise ValueError('Classes incompatibles.')
            log_root.mkdir(parents=True,exist_ok=True)
            logger=logging.getLogger(f'churn-predictions-{uuid.uuid4().hex}')
            logger.setLevel(logging.INFO);logger.propagate=False
            handler=RotatingFileHandler(log_root/'predictions.jsonl',maxBytes=5_000_000,backupCount=3,encoding='utf-8')
            handler.setFormatter(logging.Formatter('%(message)s'));logger.addHandler(handler)
            app.state.logger=logger;app.state.handler=handler
            app.state.model=model;app.state.metadata=metadata
            app.state.model_version=metadata['model_version'];app.state.ready=True
        except Exception as exc:
            # Pas de chemin interne ni d'entrée client dans la réponse publique.
            app.state.load_error_type=type(exc).__name__
        yield
        if app.state.handler:
            app.state.handler.flush();app.state.handler.close()
            app.state.logger.removeHandler(app.state.handler)

    api=FastAPI(title='Assurance Churn API',version='1.0.0',lifespan=lifespan,
        description='Prévision de churn à 3 mois. Score non calibré ; usage de démonstration.')

    @api.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        # Évite la réémission d'un NaN/Infinity ou d'un payload brut dans une erreur.
        errors=[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422,content={'detail':errors})

    @api.get('/health')
    def health():
        if not api.state.ready:
            return JSONResponse(status_code=503,content={'status':'unavailable','model_version':None})
        return {'status':'ok','model_version':api.state.model_version}

    @api.post('/predict',response_model=PredictionOutput)
    def predict(payload: PredictionInput):
        if not api.state.ready:
            raise HTTPException(status_code=503,detail='Modèle indisponible.')
        t=time.perf_counter();request_id=uuid.uuid4().hex
        data=payload.model_dump()
        try:
            p=float(api.state.model.predict_proba(pd.DataFrame([data]))[0,1])
            if not np.isfinite(p) or not 0<=p<=1:
                raise ValueError('Probabilité invalide.')
        except Exception as exc:
            raise HTTPException(status_code=500,detail='Échec de la prédiction.') from exc
        meta=api.state.metadata
        result=PredictionOutput(client_id=payload.client_id,churn_probability=p,
            prediction=int(p>=meta['threshold']),
            risk_level=risk_level(p,meta['risk_bounds']['moderate'],meta['risk_bounds']['high']))
        # L'identifiant brut et les dates ne sont pas nécessaires au suivi de drift.
        inputs={k:v for k,v in data.items() if k not in {'client_id','date_souscription','date_derniere_interaction'}}
        output=result.model_dump(exclude={'client_id'})
        record={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'request_id':request_id,
            'model_version':api.state.model_version,'duration_ms':(time.perf_counter()-t)*1000,
            'status':'ok','inputs':inputs,'output':output,'threshold':meta['threshold']}
        api.state.logger.info(json.dumps(record,ensure_ascii=False,allow_nan=False))
        return result
    return api

app=create_app()
