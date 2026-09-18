"""Contrat explicite : features brutes, pas de cible ni de features calculées."""
from __future__ import annotations
from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictInt, StrictStr, field_validator, model_validator


def numeric_only(value):
    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float))):
        raise ValueError('Un nombre JSON est requis, sans chaîne ni booléen.')
    return value

Count=Annotated[StrictInt,Field(ge=0,le=2147483647)]
Number=Annotated[float,BeforeValidator(numeric_only),Field(ge=0,le=1e15,allow_inf_nan=False)]
Text=Annotated[StrictStr,Field(min_length=1,max_length=160)]

class PredictionInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    client_id: Annotated[StrictStr,Field(min_length=1,max_length=100)]
    age: Count
    situation_familiale: Text
    profession: Text
    region: Text
    anciennete_mois: Count
    produit_principal: Text
    niveau_couverture: Text
    canal_souscription: Text
    prime_mensuelle_eur: Number
    nb_sinistres_12m: Count
    montant_sinistres_eur: Number
    nb_appels_support_12m: Number | None = None
    nb_avenants_contrat: Count
    retard_paiement_nb: Count
    score_satisfaction: Annotated[float,BeforeValidator(numeric_only),Field(ge=1,le=5,allow_inf_nan=False)] | None = None
    resiliation_anterieure: Annotated[StrictInt,Field(ge=0,le=1)]
    date_souscription: str | None = None
    date_derniere_interaction: str | None = None

    @field_validator('date_souscription','date_derniere_interaction')
    @classmethod
    def iso_date(cls,value):
        if value is not None:
            parsed=date.fromisoformat(value)
            if parsed.isoformat()!=value:
                raise ValueError('Utiliser le format YYYY-MM-DD.')
        return value

    @model_validator(mode='after')
    def consistent_dates(self):
        if self.date_souscription and self.date_derniere_interaction:
            if self.date_derniere_interaction < self.date_souscription:
                raise ValueError('La dernière interaction précède la souscription.')
        return self

class PredictionOutput(BaseModel):
    client_id: str
    churn_probability: Annotated[float,Field(ge=0,le=1,allow_inf_nan=False)]
    prediction: Literal[0,1]
    risk_level: Literal['faible','modéré','élevé']
