"""Agent: enrichit 1 lead avec l'API Pappers → PappersEnrichment."""
import logging
from typing import TypedDict

from apps.leadcommercial.pappers_client import PappersEnrichment, fetch_enrichment

logger = logging.getLogger(__name__)


class EnrichInput(TypedDict):
    """Input for enrich_lead."""

    siren: str


def enrich_lead(params: EnrichInput) -> PappersEnrichment:
    """Enrich a lead by fetching dirigeant, site_web and capital from Pappers.

    Delegates to pappers_client.fetch_enrichment.
    Returns empty strings / None on any API error (graceful degradation).
    """
    enrichment = fetch_enrichment(params["siren"])
    logger.debug("pappers_enricher: siren=%s enrichi", params["siren"])
    return enrichment
