"""python -m partie1_ml.train : CV sur train, test gelé, SHAP, artefact complet.

La sélection utilise l'Average Precision moyenne en CV stratifiée à 5 folds.
Le seuil 0,5 est fixé avant exécution. Pas de réentraînement sur le holdout.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score,brier_score_loss,confusion_matrix,
    f1_score,precision_score,recall_score,roc_auc_score,RocCurveDisplay,
    PrecisionRecallDisplay,ConfusionMatrixDisplay)
from sklearn.model_selection import GridSearchCV,StratifiedKFold,train_test_split
from threadpoolctl import threadpool_limits
from partie1_ml.features import make_pipeline, REQUIRED, RAW_NUMERIC, CATEGORICAL

ROOT=Path(__file__).resolve().parents[1]
SEED=42
THRESHOLD=0.5

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def scores(y,p,threshold=THRESHOLD):
    pred=np.asarray(p)>=threshold
    return {'auc_roc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),
        'precision':float(precision_score(y,pred,zero_division=0)),
        'recall':float(recall_score(y,pred,zero_division=0)),
        'f1':float(f1_score(y,pred,zero_division=0)),'brier':float(brier_score_loss(y,p)),
        'threshold':threshold,'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist(),
        'n':len(y),'positive_support':int(np.sum(y))}

def dataset_audit(df):
    expected=set(REQUIRED+['client_id','date_souscription','date_derniere_interaction','churned'])
    if set(df.columns)!=expected: raise ValueError(f'Schéma inattendu : {set(df.columns)^expected}')
    if df.client_id.duplicated().any(): raise ValueError('Clients répétés : résoudre avant split.')
    if df.churned.isna().any() or set(df.churned.unique())!={0,1}: raise ValueError('Cible non binaire.')
    for c in RAW_NUMERIC:
        a=df[c].dropna()
        if not np.isfinite(a).all() or (a<0).any(): raise ValueError(f'Valeurs impossibles : {c}')
    if not df.score_satisfaction.dropna().between(1,5).all(): raise ValueError('Satisfaction hors 1-5.')
    sub=pd.to_datetime(df.date_souscription,format='%Y-%m-%d',errors='raise')
    last=pd.to_datetime(df.date_derniere_interaction,format='%Y-%m-%d',errors='raise')
    return {'rows':len(df),'columns':len(df.columns),'positive_count':int(df.churned.sum()),
        'churn_rate':float(df.churned.mean()),'duplicate_clients':int(df.client_id.duplicated().sum()),
        'missing':{k:int(v) for k,v in df.isna().sum().items()},
        'interaction_before_subscription':int((last<sub).sum()),
        'date_souscription_range':[sub.min().date().isoformat(),sub.max().date().isoformat()],
        'date_derniere_interaction_range':[last.min().date().isoformat(),last.max().date().isoformat()],
        'dates_used_as_features':False,
        'warning':"Date d'observation absente. Ancienneté déclarée non reconstruite depuis les dates."}

def explore(train,out,figures):
    train.describe(include='all').to_csv(out/'description_train.csv')
    q1,q3=train.montant_sinistres_eur.quantile([.25,.75]);bound=float(q3+1.5*(q3-q1))
    write_json(out/'eda.json',{'n_train':len(train),'churn_rate_train':float(train.churned.mean()),
        'sinistres_iqr_upper_train':bound,'sinistres_above_iqr_train':int((train.montant_sinistres_eur>bound).sum()),
        'sinistres_max_train':float(train.montant_sinistres_eur.max()),
        'treatment':'Aucune suppression ni winsorisation : log1p du montant dans la pipeline.',
        'missing_train':{k:int(v) for k,v in train.isna().sum().items()}})
    for col in CATEGORICAL:
        train.groupby(col,dropna=False).churned.agg(['count','mean']).to_csv(out/f'churn_par_{col}_train.csv')
    for col in ['age','anciennete_mois','montant_sinistres_eur','score_satisfaction','nb_appels_support_12m']:
        fig,ax=plt.subplots(figsize=(7.8,4.5))
        for label in [0,1]: ax.hist(train.loc[train.churned==label,col].dropna(),bins=22,alpha=.55,label=f'Churn = {label}')
        ax.set_title(f'Distribution sur entraînement : {col}');ax.set_xlabel(col);ax.set_ylabel('Nombre de clients');ax.legend()
        fig.tight_layout();fig.savefig(figures/f'distribution_{col}.png',dpi=130);plt.close(fig)

def explain_model(model,X_train,X_test,y_test,out,figures):
    imp=permutation_importance(model,X_test,y_test,scoring='average_precision',n_repeats=10,random_state=SEED,n_jobs=1)
    perm=pd.DataFrame({'feature':X_test.columns,'importance_mean':imp.importances_mean,'importance_std':imp.importances_std}).sort_values('importance_mean',ascending=False)
    perm.to_csv(out/'permutation_importance.csv',index=False)
    top=perm.head(10).iloc[::-1];fig,ax=plt.subplots(figsize=(8,5))
    ax.barh(top.feature,top.importance_mean,xerr=top.importance_std)
    ax.set_xlabel("Baisse d'Average Precision après permutation");ax.set_title('Importance des variables brutes — holdout gelé')
    fig.tight_layout();fig.savefig(figures/'permutation_importance.png',dpi=150);plt.close(fig)
    import shap
    pre=model[:-1];names=pre.get_feature_names_out()
    background=np.asarray(pre.transform(X_train.sample(min(100,len(X_train)),random_state=SEED)))
    evaluation=np.asarray(pre.transform(X_test.sample(min(120,len(X_test)),random_state=SEED)))
    clf=model.named_steps['model']
    if isinstance(clf,RandomForestClassifier):
        values=shap.TreeExplainer(clf).shap_values(evaluation)
        if isinstance(values,list): values=values[1]
        if values.ndim==3: values=values[:,:,1]
        scale='contribution à la probabilité brute du classifieur'
    else:
        values=shap.LinearExplainer(clf,background).shap_values(evaluation)
        scale='contribution au log-odds du classifieur'
    order=np.argsort(np.abs(values).mean(axis=0))[::-1]
    tab=pd.DataFrame({'feature':names[order],'mean_abs_shap':np.abs(values).mean(axis=0)[order]})
    tab.to_csv(out/'shap_importance.csv',index=False)
    # Graphique matplotlib direct : aucune dépendance au style SHAP.
    top=tab.head(15).iloc[::-1];fig,ax=plt.subplots(figsize=(9,6))
    ax.barh(top.feature,top.mean_abs_shap);ax.set_xlabel('Moyenne de |SHAP|')
    ax.set_title('SHAP — 120 observations du holdout');fig.tight_layout()
    fig.savefig(figures/'shap_importance.png',dpi=150);plt.close(fig)
    return {'method':'SHAP + permutation','shap_scale':scale,'n_explained':len(evaluation),
        'shap_top5':tab.head(5).to_dict(orient='records'),'permutation_top5':perm.head(5).to_dict(orient='records'),
        'warning':'Associations non causales ; les corrélations peuvent partager les importances.'}

def run(csv,root=ROOT):
    started=time.perf_counter();out=root/'partie1_ml/outputs';figures=root/'docs/figures'
    out.mkdir(parents=True,exist_ok=True);figures.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(csv);write_json(out/'dataset_audit.json',dataset_audit(df))
    train_idx,test_idx=train_test_split(np.arange(len(df)),test_size=.2,stratify=df.churned,random_state=SEED)
    train,test=df.iloc[train_idx].copy(),df.iloc[test_idx].copy()
    X_train,y_train=train.drop(columns='churned'),train.churned
    X_test,y_test=test.drop(columns='churned'),test.churned
    explore(train,out,figures)
    write_json(out/'split_manifest.json',{'seed':SEED,'train_client_ids':train.client_id.tolist(),'test_client_ids':test.client_id.tolist()})
    cv=StratifiedKFold(5,shuffle=True,random_state=SEED)
    candidates={
        'logistic_regression':(LogisticRegression(max_iter=2500,class_weight='balanced',random_state=SEED),{'model__C':[.03,.1,.3,1.,3.]}),
        'random_forest':(RandomForestClassifier(n_estimators=180,class_weight='balanced',random_state=SEED,n_jobs=1),{'model__max_depth':[6,None],'model__min_samples_leaf':[3,8],'model__max_features':['sqrt',.7]})}
    fitted={};comparison={}
    for name,(estimator,grid) in candidates.items():
        t=time.perf_counter();print('TRAIN',name,flush=True)
        search=GridSearchCV(make_pipeline(estimator),grid,scoring={'ap':'average_precision','auc':'roc_auc'},refit='ap',cv=cv,n_jobs=2,error_score='raise')
        search.fit(X_train,y_train);pd.DataFrame(search.cv_results_).to_csv(out/f'cv_{name}.csv',index=False)
        i=search.best_index_
        comparison[name]={'best_parameters':search.best_params_,
            'cv_ap_mean':float(search.cv_results_['mean_test_ap'][i]),'cv_ap_std':float(search.cv_results_['std_test_ap'][i]),
            'cv_auc_mean':float(search.cv_results_['mean_test_auc'][i]),'fit_seconds':time.perf_counter()-t}
        fitted[name]=search.best_estimator_
    selected=max(comparison,key=lambda n:comparison[n]['cv_ap_mean'])
    print('SELECTED_BEFORE_TEST',selected,flush=True)
    for name,model in fitted.items():
        p=model.predict_proba(X_test)[:,list(model.classes_).index(1)]
        comparison[name]['holdout']=scores(y_test,p)
        pd.DataFrame({'client_id':test.client_id,'y_true':y_test,'probability':p,'prediction':(p>=THRESHOLD).astype(int)}).to_csv(out/f'predictions_{name}.csv',index=False)
    baseline=scores(y_test,DummyClassifier(strategy='prior').fit(X_train,y_train).predict_proba(X_test)[:,1])
    model=fitted[selected];p=model.predict_proba(X_test)[:,1]
    for kind,display in [('roc',RocCurveDisplay),('precision_recall',PrecisionRecallDisplay)]:
        fig,ax=plt.subplots(figsize=(6.5,5))
        for name,m in fitted.items(): display.from_predictions(y_test,m.predict_proba(X_test)[:,1],name=name,ax=ax)
        ax.set_title('Comparaison finale — holdout');fig.tight_layout();fig.savefig(figures/f'{kind}.png',dpi=130);plt.close(fig)
    fig,ax=plt.subplots(figsize=(5.8,5));ConfusionMatrixDisplay.from_predictions(y_test,p>=THRESHOLD,display_labels=['Reste','Résilie'],ax=ax,colorbar=False)
    ax.set_title(f'{selected} — seuil {THRESHOLD}');fig.tight_layout();fig.savefig(figures/'confusion_matrix.png',dpi=130);plt.close(fig)
    explanation=explain_model(model,X_train,X_test,y_test,out,figures)
    rng=np.random.default_rng(SEED);aucs=[];yt=y_test.to_numpy()
    for _ in range(500):
        idx=rng.integers(0,len(yt),len(yt))
        if len(np.unique(yt[idx]))==2: aucs.append(roc_auc_score(yt[idx],p[idx]))
    digest=hashlib.sha256(csv.read_bytes()).hexdigest();artifact=root/'partie1_ml/model.joblib'
    joblib.dump(model,artifact,compress=3)
    assert np.allclose(joblib.load(artifact).predict_proba(X_test),model.predict_proba(X_test),rtol=0,atol=1e-12)
    metadata={'model_version':f'1.0.0-{digest[:10]}','created_utc':datetime.now(timezone.utc).isoformat(),
        'selected_model':selected,'selection_metric':'mean 5-fold stratified CV average_precision on training only',
        'dataset_sha256':digest,'model_sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
        'python':platform.python_version(),'packages':{n:version(n) for n in ['scikit-learn','numpy','pandas','scipy','joblib']},
        'threshold':THRESHOLD,'risk_bounds':{'moderate':.25,'high':THRESHOLD},
        'risk_policy':'Illustratif : faible < 0,25 ; modéré [0,25;0,5[ ; élevé >= 0,5.',
        'input_features':REQUIRED,'dropped':['client_id','date_souscription','date_derniere_interaction'],
        'seed':SEED,'train_size':len(train),'test_size':len(test),'trained_on_holdout':False,
        'probabilities_calibrated':False,'metrics':comparison[selected]['holdout'],
        'holdout_auc_bootstrap_95_percentile':np.quantile(aucs,[.025,.975]).tolist()}
    write_json(root/'partie1_ml/metadata.json',metadata)
    result={'selected_model':selected,'candidates':comparison,'dummy_baseline':baseline,'interpretability':explanation,'total_seconds':time.perf_counter()-started}
    write_json(out/'metrics.json',result)
    reference={}
    for c in ['montant_sinistres_eur','score_satisfaction','nb_appels_support_12m','anciennete_mois']:
        arr=train[c].dropna().to_numpy();edges=np.unique(np.quantile(arr,np.linspace(0,1,11)))[1:-1].tolist()
        counts=np.histogram(arr,bins=[-np.inf]+edges+[np.inf])[0].tolist()+[int(train[c].isna().sum())]
        reference[c]={'finite_edges':edges,'counts':counts,'n':len(train)}
    write_json(root/'partie1_ml/drift_reference.json',reference)
    example={'client_id':'DEMO-001','age':45,'situation_familiale':'Marié(e)','profession':'Salarié',
        'region':'Île-de-France','anciennete_mois':48,'produit_principal':'Assurance Auto',
        'niveau_couverture':'Confort','canal_souscription':'Web','prime_mensuelle_eur':95.0,
        'nb_sinistres_12m':1,'montant_sinistres_eur':1500.0,'nb_appels_support_12m':2.0,
        'nb_avenants_contrat':1,'retard_paiement_nb':0,'score_satisfaction':4.0,
        'resiliation_anterieure':0,'date_souscription':'2022-01-01','date_derniere_interaction':'2024-02-15'}
    write_json(root/'partie3_mlops/example_request.json',example)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--csv',type=Path,default=ROOT/'data/dataset_assurance_churn.csv')
    with threadpool_limits(limits=2): run(p.parse_args().csv)
