"""Scorer ICP JM Partners — signal-based.

Signal de départ détermine le score de base ; les modificateurs ajustent
en fonction de la fraîcheur de la création et de la forme juridique.

Seuils :
  ≥ 75 → CHAUD  |  50–74 → TIÈDE  |  30–49 → FROID  |  < 30 → EXCLU
"""

from __future__ import annotations

from datetime import date
from typing import Any

SIGNAL_BASE_SCORES: dict[str, int] = {
    "creation": 100,
    "rattrapage": 80,
    "intention": 60,
    "changement_dirigeant": 70,
}

# Codes catégorie juridique INSEE considérés comme formes prioritaires ICP
FORMES_PRIORITAIRES: set[str] = {
    "5499",  # SARL
    "5710",  # SAS
    "5720",  # SASU
    "5498",  # EURL
    "1000",  # Entrepreneur individuel / AE
    "5202",  # SARL
    "5203",  # SARL
}

QUALIFICATION_THRESHOLD = 50
SEUIL_CHAUD = 75
SEUIL_TIEDE = 50


def score_lead(company: dict[str, Any], signal: str) -> dict[str, Any]:
    """Calcule le score ICP d'un lead à partir d'un signal de détection.

    Args:
        company: Dictionnaire avec les champs SIREN, denomination,
                 forme_juridique (code INSEE), dept, date_creation.
        signal:  Type de signal : 'creation', 'rattrapage', 'intention',
                 'changement_dirigeant'.

    Returns:
        Dictionnaire avec score (int), qualified (bool), scoring_details (list[str]),
        signal (str), qualification (str), siren (str).
    """
    base = SIGNAL_BASE_SCORES.get(signal, 60)
    score = base
    details: list[str] = []

    # Malus forme juridique non prioritaire
    if company.get("forme_juridique") not in FORMES_PRIORITAIRES:
        score -= 10
        details.append("-10 (forme juridique non prioritaire)")

    # Bonus fraîcheur de création
    date_creation_str = company.get("date_creation")
    if date_creation_str:
        created = date.fromisoformat(date_creation_str)
        days_ago = (date.today() - created).days
        if days_ago <= 7:
            score += 10
            details.append("+10 (création très récente ≤ 7j)")
        elif days_ago <= 14:
            score += 5
            details.append("+5 (création récente 7–14j)")

    qualified = score >= QUALIFICATION_THRESHOLD

    if score >= SEUIL_CHAUD:
        qualification = "CHAUD"
    elif score >= SEUIL_TIEDE:
        qualification = "TIÈDE"
    elif score >= 30:
        qualification = "FROID"
    else:
        qualification = "EXCLU"

    return {
        "siren": company.get("siren"),
        "denomination": company.get("denomination"),
        "score": score,
        "qualified": qualified,
        "qualification": qualification,
        "scoring_details": details,
        "signal": signal,
    }


def score_batch(companies: list[dict[str, Any]], signal: str) -> list[dict[str, Any]]:
    """Applique score_lead à une liste de sociétés."""
    return [score_lead(c, signal) for c in companies]
