"""Contrats du feature engineering ; les lignes sont des fixtures synthétiques."""
import importlib.util
import numpy as np
import pandas as pd
import pytest

def test_feature_module_exists():
    assert importlib.util.find_spec('partie1_ml.features') is not None

@pytest.fixture
def row():
    return {'client_id':'TEST', 'age':45, 'situation_familiale':'Marié(e)',
            'profession':'Salarié', 'region':'Inconnue', 'anciennete_mois':24,
            'produit_principal':'Assurance Auto', 'niveau_couverture':'Confort',
            'canal_souscription':'Web', 'prime_mensuelle_eur':95., 'nb_sinistres_12m':2,
            'montant_sinistres_eur':1000., 'nb_appels_support_12m':3.,
            'nb_avenants_contrat':1, 'retard_paiement_nb':2, 'score_satisfaction':2.,
            'resiliation_anterieure':1, 'date_souscription':'2023-01-01',
            'date_derniere_interaction':'2024-01-02'}

def test_business_formulas(row):
    from partie1_ml.features import BusinessFeatures
    out = BusinessFeatures().fit_transform(pd.DataFrame([row]))
    assert out.loc[0,'support_par_sinistre_lisse'] == 1.
    assert out.loc[0,'tension_relationnelle'] == 9.
    assert out.loc[0,'retards_x_resiliation'] == 2.
    assert out.loc[0,'log_montant_sinistres'] == pytest.approx(np.log1p(1000))
    assert not {'client_id','churned','date_souscription','date_derniere_interaction'} & set(out)

def test_missing_values_preserved_until_imputer(row):
    from partie1_ml.features import BusinessFeatures
    row.update(nb_appels_support_12m=None,score_satisfaction=None)
    out=BusinessFeatures().fit_transform(pd.DataFrame([row]))
    assert np.isnan(out.loc[0,'tension_relationnelle'])

def test_zero_denominator_finite_and_input_unchanged(row):
    from partie1_ml.features import BusinessFeatures
    row.update(nb_sinistres_12m=0,anciennete_mois=0)
    x=pd.DataFrame([row]); before=x.copy(deep=True)
    out=BusinessFeatures().fit_transform(x)
    assert out.loc[0,'support_par_sinistre_lisse']==3
    assert np.isfinite(out.select_dtypes('number').to_numpy()).all()
    pd.testing.assert_frame_equal(x,before)

def test_pipeline_imputes_unknown_categories_without_leakage(row):
    from partie1_ml.features import make_pipeline
    from sklearn.linear_model import LogisticRegression
    xs=pd.DataFrame([row,{**row,'age':60,'score_satisfaction':None,'nb_appels_support_12m':None}])
    m=make_pipeline(LogisticRegression()).fit(xs,[0,1])
    assert np.isfinite(m.predict_proba(pd.DataFrame([{**row,'profession':'Nouvelle catégorie'}]))).all()
    assert 'client_id' not in m.named_steps['features'].get_feature_names_out()

def test_target_is_rejected(row):
    from partie1_ml.features import BusinessFeatures
    with pytest.raises(ValueError,match='churned'):
        BusinessFeatures().fit_transform(pd.DataFrame([{**row,'churned':1}]))
