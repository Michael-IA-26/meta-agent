import logging
import os
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

PAPPERS_API_KEY = os.getenv("PAPPERS_API_KEY", "")
PAPPERS_BASE_URL = "https://api.pappers.fr/v2"


class PappersEnrichment(TypedDict):
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def fetch_enrichment(siren: str) -> PappersEnrichment:
    """Fetch dirigeant, site_web and capital_social from Pappers for a given SIREN."""
    empty: PappersEnrichment = {
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }

    if not PAPPERS_API_KEY:
        logger.warning("PAPPERS_API_KEY manquant — enrichissement desactive")
        return empty

    try:
        response = httpx.get(
            f"{PAPPERS_BASE_URL}/entreprise",
            params={"siren": siren, "api_token": PAPPERS_API_KEY},
            timeout=10,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Erreur Pappers {e.response.status_code} pour {siren}: "
            f"{e.response.text[:200]}"
        )
        return empty
    except httpx.RequestError as e:
        logger.error(f"Erreur reseau Pappers pour {siren}: {e}")
        return empty

    return _parse_enrichment(response.json())


def _parse_enrichment(data: dict) -> PappersEnrichment:
    """Extract enrichment fields from a raw Pappers API response."""
    dirigeants = data.get("dirigeants", [])
    dirigeant = dirigeants[0] if dirigeants else {}
    return {
        "dirigeant_nom": dirigeant.get("nom") or "",
        "dirigeant_prenom": dirigeant.get("prenom") or "",
        "dirigeant_email": dirigeant.get("email") or "",
        "site_web": data.get("site_web") or "",
        "capital_social": data.get("capital"),
    }
