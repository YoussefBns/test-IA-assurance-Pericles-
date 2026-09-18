"""Transformations métier partagées ; statistiques apprises uniquement au fit."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.utils.validation import check_is_fitted

CATEGORICAL = [
    'situation_familiale', 'profession', 'region', 'produit_principal',
    'niveau_couverture', 'canal_souscription',
]
RAW_NUMERIC = [
    'age', 'anciennete_mois', 'prime_mensuelle_eur', 'nb_sinistres_12m',
    'montant_sinistres_eur', 'nb_appels_support_12m', 'nb_avenants_contrat',
    'retard_paiement_nb', 'score_satisfaction', 'resiliation_anterieure',
]
DERIVED = [
    'support_par_sinistre_lisse', 'tension_relationnelle',
    'retards_x_resiliation', 'log_montant_sinistres',
]
NUMERIC = [c for c in RAW_NUMERIC if c != 'montant_sinistres_eur'] + DERIVED
REQUIRED = RAW_NUMERIC + CATEGORICAL


class BusinessFeatures(TransformerMixin, BaseEstimator):
    """Trois signaux métier et un traitement des extrêmes.

    Support/(1+sinistres 12m) : contacts relativement aux sinistres.
    (5-satisfaction)*appels : interaction insatisfaction/contact.
    Retards*résiliation antérieure : cumul de difficultés contractuelles.
    log1p(montant) : atténuation de la queue, sans suppression de dossiers.
    Proxies non causaux ; aucune rentabilité ni date d'observation inventée.
    """

    def fit(self, X: pd.DataFrame, y=None):
        self._validate(X)
        self.feature_names_in_ = np.array(X.columns, dtype=object)
        self.n_features_in_ = len(X.columns)
        self.fitted_ = True
        return self

    @staticmethod
    def _validate(X):
        if not isinstance(X, pd.DataFrame):
            raise TypeError('BusinessFeatures attend un DataFrame.')
        if 'churned' in X.columns:
            raise ValueError('La cible churned ne doit jamais être une feature.')
        missing = sorted(set(REQUIRED) - set(X.columns))
        if missing:
            raise ValueError(f'Features manquantes : {missing}')

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        check_is_fitted(self, 'fitted_')
        self._validate(X)
        # Sélection explicite : identifiants et dates ne peuvent pas être appris.
        out = X[REQUIRED].copy()
        for column in RAW_NUMERIC:
            out[column] = pd.to_numeric(out[column], errors='raise').astype(float)
        for column in ['montant_sinistres_eur', 'nb_sinistres_12m']:
            if (out[column].dropna() < 0).any():
                raise ValueError(f'{column} doit être non négatif.')

        # Les manques se propagent ; l'imputation n'a lieu qu'en aval dans le fold.
        out['support_par_sinistre_lisse'] = (
            out.nb_appels_support_12m / (1 + out.nb_sinistres_12m)
        )
        out['tension_relationnelle'] = (
            (5 - out.score_satisfaction) * out.nb_appels_support_12m
        )
        out['retards_x_resiliation'] = (
            out.retard_paiement_nb * out.resiliation_anterieure
        )
        out['log_montant_sinistres'] = np.log1p(out.montant_sinistres_eur)
        return out[NUMERIC + CATEGORICAL]

    def get_feature_names_out(self, input_features=None):
        return np.array(NUMERIC + CATEGORICAL, dtype=object)


def make_pipeline(estimator) -> Pipeline:
    """Créer un pipeline non ajusté à apprendre entièrement dans chaque fold."""
    numerical = Pipeline([
        ('imputer', SimpleImputer(
            strategy='median', add_indicator=True, keep_empty_features=True,
        )),
        ('scaler', StandardScaler()),
    ])
    categorical = Pipeline([
        ('imputer', SimpleImputer(strategy='most_frequent', keep_empty_features=True)),
        ('encoder', OneHotEncoder(handle_unknown='ignore', sparse_output=False)),
    ])
    preprocessor = ColumnTransformer([
        ('num', numerical, NUMERIC),
        ('cat', categorical, CATEGORICAL),
    ])
    return Pipeline([
        ('features', BusinessFeatures()),
        ('preprocessor', preprocessor),
        ('model', estimator),
    ])
