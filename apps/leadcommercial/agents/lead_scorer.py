"""Agent: score 1 entreprise via scorer.py → ScoredLead."""
import logging
from typing import TypedDict

from apps.leadcommercial.agents.sirene_fetcher import CompanyRaw
from apps.leadcommercial.scorer import IcpContext, ScoredLead, score_lead

logger = logging.getLogger(__name__)


class ScoreInput(TypedDict):
    """Input for score_company."""

    company: CompanyRaw
    signal_type: str
    icp: IcpContext | None


def score_company(params: ScoreInput) -> ScoredLead:
    """Score a single company using optional ICP rules from Supabase.

    Returns a ScoredLead with score, signal_type, scoring_details,
    qualified flag, and empty enrichment placeholders (filled by
    pappers_enricher downstream).
    """
    result = score_lead(params["company"], params["signal_type"], icp=params["icp"])  # type: ignore[arg-type]
    logger.debug(
        "lead_scorer: %s — score %d",
        params["company"].get("denomination", "N/A"),
        result["score"],
    )
    return result
