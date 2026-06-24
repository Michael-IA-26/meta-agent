"""Schéma Pydantic pour la configuration LeadHunter.

Ce module est le contrat partagé entre le YAML local, le futur frontend Supabase,
et le pipeline. Le pipeline reçoit toujours un LeadHunterConfig déjà validé.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

# Correspondance tranche INSEE → (borne basse, borne haute inclusive).
# "NN" = non renseigné, géré séparément via inclure_effectif_non_renseigne.
_TRANCHES_NUMERIQUES: list[tuple[str, int, int]] = [
    ("00", 0, 0),
    ("01", 1, 2),
    ("02", 3, 5),
    ("03", 6, 9),
    ("11", 10, 19),
    ("12", 20, 49),
    ("21", 50, 99),
    ("22", 100, 199),
    ("31", 200, 249),
    ("32", 250, 499),
    ("41", 500, 999),
    ("42", 1000, 1999),
    ("51", 2000, 4999),
    ("52", 5000, 9999),
    ("53", 10000, 999999),
]


def effectif_codes(min_sal: int | None, max_sal: int | None) -> list[str]:
    """Retourne les codes tranches INSEE couverts par [min_sal, max_sal].

    Une tranche est incluse si elle chevauche l'intervalle.
    None côté min = pas de borne basse ; None côté max = pas de borne haute.
    "NN" (non renseigné) n'est PAS retourné ici — il est géré via
    inclure_effectif_non_renseigne dans CriteresRecherche.effectif_tranches().
    """
    result = []
    for code, low, high in _TRANCHES_NUMERIQUES:
        below_max = max_sal is None or low <= max_sal
        above_min = min_sal is None or high >= min_sal
        if above_min and below_max:
            result.append(code)
    return result


class CriteresRecherche(BaseModel):
    codes_postaux: list[str]
    anciennete_jours: int | None = None
    date_creation_min: date | None = None
    date_creation_max: date | None = None
    naf_exclus: list[str] = []
    effectif_min: int | None = None
    effectif_max: int | None = None
    inclure_effectif_non_renseigne: bool = True
    formes_juridiques_incluses: list[str] = []
    formes_juridiques_exclues: list[str] = []

    @field_validator("codes_postaux")
    @classmethod
    def au_moins_un_code_postal(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("codes_postaux doit contenir au moins un code postal")
        return v

    @model_validator(mode="after")
    def anciennete_et_dates_mutuellement_exclusifs(self) -> "CriteresRecherche":
        has_anciennete = self.anciennete_jours is not None
        has_dates = self.date_creation_min is not None or self.date_creation_max is not None
        if has_anciennete and has_dates:
            raise ValueError(
                "anciennete_jours et date_creation_min/max sont mutuellement exclusifs — "
                "utilise l'un ou l'autre, pas les deux"
            )
        return self

    def effectif_tranches(self) -> list[str]:
        """Retourne les codes tranches INSEE autorisés selon effectif_min/max.

        Inclut "NN" (effectif non renseigné) si inclure_effectif_non_renseigne=True.
        Retourne une liste vide (= pas de filtre effectif) si effectif_min et
        effectif_max sont tous les deux None et inclure_effectif_non_renseigne=True,
        car aucun filtre n'est souhaité.
        """
        no_bounds = self.effectif_min is None and self.effectif_max is None
        if no_bounds and self.inclure_effectif_non_renseigne:
            return []  # pas de filtre effectif — tout passe
        codes = effectif_codes(self.effectif_min, self.effectif_max)
        if self.inclure_effectif_non_renseigne:
            codes = ["NN", ""] + codes
        return codes


class SeuilsScoring(BaseModel):
    chaud_min: int = 75
    tiede_min: int = 50
    exclu_max: int = 30

    @model_validator(mode="after")
    def coherence_seuils(self) -> "SeuilsScoring":
        if not (self.exclu_max < self.tiede_min < self.chaud_min):
            raise ValueError(
                f"Seuils incohérents : exclu_max ({self.exclu_max}) doit être < "
                f"tiede_min ({self.tiede_min}) doit être < chaud_min ({self.chaud_min})"
            )
        return self


class LeadHunterConfig(BaseModel):
    recherche: CriteresRecherche
    scoring: SeuilsScoring = SeuilsScoring()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LeadHunterConfig":
        return cls.model_validate(data)
