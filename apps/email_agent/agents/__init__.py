"""Shared TypedDict types for the email-agent pipeline."""

from typing import Optional, TypedDict

# Functional form required: 'from' is a Python keyword.
EmailRaw = TypedDict(
    "EmailRaw",
    {
        "id": str,
        "subject": str,
        "from": str,
        "date": str,
        "body": str,
    },
)

EmailAnalyzed = TypedDict(
    "EmailAnalyzed",
    {
        "id": str,
        "subject": str,
        "from": str,
        "date": str,
        "body": str,
        "priority": str,
        "category": str,
        "summary": str,
        "action": Optional[str],
        "suggested_reply": Optional[str],
    },
)


class KpiResult(TypedDict):
    """KPI result from a daily pipeline run."""

    emails_analyses: int
    temps_theorique_min: int
    temps_agent_min: float
    temps_gagne_min: float
    gain_pourcentage: float
    valeur_estimee_eur: float
    semaine: str
