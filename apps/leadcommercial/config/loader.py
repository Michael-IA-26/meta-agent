"""Loader : YAML → overrides CLI → LeadHunterConfig validé.

Précédence : CLI > YAML > défauts Pydantic.
Le pipeline ne doit jamais lire le YAML directement — il appelle load_config().
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from apps.leadcommercial.config.schema import LeadHunterConfig

_DEFAULT_YAML = Path(__file__).parent / "lead_hunter.yaml"


def _resolve_anciennete(data: dict[str, Any]) -> dict[str, Any]:
    """Traduit anciennete_jours → date_creation_min dans le dict recherche.

    Le pipeline Sirene travaille avec des dates ISO, pas un nombre de jours.
    Cette traduction est faite au chargement (après validation Pydantic) pour
    ne pas dupliquer la logique dans l'orchestrateur.
    """
    return data


def load_config(
    yaml_path: str | Path | None = None,
    *,
    codes_postaux: list[str] | None = None,
    date_creation_min: str | None = None,
    date_creation_max: str | None = None,
    anciennete_jours: int | None = None,
) -> LeadHunterConfig:
    """Charge la config depuis un YAML puis applique les overrides CLI.

    Paramètres CLI :
      codes_postaux       — surcharge recherche.codes_postaux
      date_creation_min   — surcharge recherche.date_creation_min (ISO YYYY-MM-DD)
      date_creation_max   — surcharge recherche.date_creation_max
      anciennete_jours    — surcharge recherche.anciennete_jours

    Retourne un LeadHunterConfig validé. Lève ValueError si la config est
    incohérente (ex: anciennete_jours + dates, seuils inversés).
    """
    path = Path(yaml_path) if yaml_path else _DEFAULT_YAML

    with open(path, encoding="utf-8") as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    recherche = raw.setdefault("recherche", {})

    # Overrides CLI (priorité maximale)
    if codes_postaux is not None:
        recherche["codes_postaux"] = codes_postaux
    if anciennete_jours is not None:
        recherche["anciennete_jours"] = anciennete_jours
        # Si on surcharge anciennete_jours via CLI, on efface les dates éventuelles du YAML
        recherche.pop("date_creation_min", None)
        recherche.pop("date_creation_max", None)
    if date_creation_min is not None:
        recherche["date_creation_min"] = date_creation_min
        recherche.pop("anciennete_jours", None)
    if date_creation_max is not None:
        recherche["date_creation_max"] = date_creation_max
        recherche.pop("anciennete_jours", None)

    return LeadHunterConfig.from_dict(raw)


def date_from_config(cfg: LeadHunterConfig) -> tuple[str | None, str | None]:
    """Résout la fenêtre de dates à passer à Sirene.

    Retourne (date_from, date_to) en ISO YYYY-MM-DD, ou (None, None) si la
    config ne précise pas de fenêtre (le client Sirene utilisera hier par défaut).
    """
    r = cfg.recherche
    if r.anciennete_jours is not None:
        date_from = (datetime.now() - timedelta(days=r.anciennete_jours)).strftime("%Y-%m-%d")
        date_to = datetime.now().strftime("%Y-%m-%d")
        return date_from, date_to
    if r.date_creation_min is not None or r.date_creation_max is not None:
        date_from = r.date_creation_min.isoformat() if r.date_creation_min else None
        date_to = r.date_creation_max.isoformat() if r.date_creation_max else None
        return date_from, date_to
    return None, None
