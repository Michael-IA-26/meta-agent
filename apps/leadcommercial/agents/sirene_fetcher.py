"""Agent: fetch entreprises IDF depuis l'API Sirene → list[CompanyRaw]."""

import logging
from typing import TypedDict

from apps.leadcommercial.sirene_client import fetch_and_parse_idf

logger = logging.getLogger(__name__)


class CompanyRaw(TypedDict):
    """Raw company record returned by the Sirene API, filtered to IDF."""

    siren: str | None
    siret: str | None
    denomination: str
    forme_juridique: str | None
    code_naf: str | None
    dept: str
    commune: str | None
    date_creation: str | None


class SireneInput(TypedDict):
    """Input parameters for fetch_idf_companies."""

    max_results: int
    date: str | None


def fetch_idf_companies(params: SireneInput) -> list[CompanyRaw]:
    """Fetch newly created IDF establishments from the Sirene API.

    Delegates to sirene_client.fetch_and_parse_idf and returns the
    filtered list of Île-de-France companies.

    Raises ValueError if SIRENE_API_TOKEN is not configured.
    """
    companies = fetch_and_parse_idf(
        max_results=params["max_results"],
        date=params["date"],
    )
    logger.info("sirene_fetcher: %d entreprises IDF recues", len(companies))
    return companies  # type: ignore[return-value]
