"""Orchestrateur LeadCommercial.

Enchaîne les 5 agents spécialisés sans logique métier :
sirene_fetcher → lead_scorer → pappers_enricher → supabase_writer → telegram_notifier.
"""

import logging
import os
from typing import TypedDict

from apps.leadcommercial.agents.lead_scorer import ScoreInput, score_company
from apps.leadcommercial.agents.pappers_enricher import EnrichInput, enrich_lead
from apps.leadcommercial.agents.sirene_fetcher import SireneInput, fetch_idf_companies
from apps.leadcommercial.agents.supabase_writer import write_lead
from apps.leadcommercial.agents.telegram_notifier import notify_lead
from apps.leadcommercial.supabase_client import fetch_icp

logger = logging.getLogger(__name__)

SCORE_THRESHOLD = int(os.getenv("LEAD_SCORE_THRESHOLD", "50"))

_EMPTY_ENRICHMENT: dict = {
    "dirigeant_nom": "",
    "dirigeant_prenom": "",
    "dirigeant_email": "",
    "site_web": "",
    "capital_social": None,
}


class LeadEnriched(TypedDict):
    """Fully scored and enriched lead — output of orchestrator.run()."""

    siren: str | None
    siret: str | None
    denomination: str
    forme_juridique: str | None
    code_naf: str | None
    dept: str
    commune: str | None
    date_creation: str | None
    score: int
    signal_type: str
    scoring_details: list[str]
    qualified: bool
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def run(date: str | None = None, dry_run: bool = False) -> list[LeadEnriched]:
    """Run the full LeadCommercial pipeline.

    Chain of 5 agents:
    1. sirene_fetcher   — fetch IDF companies from Sirene API
    2. lead_scorer      — score each company (filters below SCORE_THRESHOLD)
    3. pappers_enricher — enrich qualified leads (dirigeant, site, capital)
    4. supabase_writer  — persist and lock (skips already-locked SIRENs)
    5. telegram_notifier — send Telegram alert for each persisted lead

    dry_run=True skips steps 4 and 5 (no Supabase writes, no Telegram alerts).
    Returns the list of qualified and persisted LeadEnriched dicts.
    """
    logger.info("Orchestrateur LeadCommercial — demarrage")

    # Setup: charger l'ICP une seule fois pour tout le batch
    icp = None
    cabinet_id = os.getenv("CABINET_ID", "")
    if not dry_run and cabinet_id:
        icp = fetch_icp(cabinet_id)
        if icp:
            logger.info("ICP charge pour cabinet %s...", cabinet_id[:8])
        else:
            logger.warning("ICP absent — scoring avec regles par defaut")

    # Etape 1 : Sirene → liste entreprises IDF
    try:
        companies = fetch_idf_companies(SireneInput(max_results=100, date=date))
    except Exception as exc:
        logger.error("sirene_fetcher echoue: %s", exc, exc_info=True)
        return []
    logger.info("Orchestrateur: %d entreprises IDF recues", len(companies))

    qualified: list[LeadEnriched] = []

    for company in companies:
        name = company.get("denomination", "N/A")
        siren = company.get("siren") or ""

        # Etape 2 : Score
        try:
            score_result = score_company(
                ScoreInput(company=company, signal_type="creation", icp=icp)
            )
        except Exception as exc:
            logger.error("lead_scorer echoue pour %s: %s", name, exc)
            continue

        if score_result["score"] < SCORE_THRESHOLD:
            continue

        # Etape 3 : Enrichissement Pappers
        try:
            enrichment = enrich_lead(EnrichInput(siren=siren))
        except Exception as exc:
            logger.warning("pappers_enricher echoue pour %s: %s", name, exc)
            enrichment = _EMPTY_ENRICHMENT  # type: ignore[assignment]

        # Fusionner : enrichment écrase les champs vides de score_result
        lead: LeadEnriched = {**company, **score_result, **enrichment}  # type: ignore[assignment]

        # Etape 4 : Persistance Supabase
        if not dry_run:
            try:
                persisted = write_lead(lead)  # type: ignore[arg-type]
            except Exception as exc:
                logger.error("supabase_writer echoue pour %s: %s", name, exc)
                continue
            if not persisted:
                continue

        qualified.append(lead)
        logger.info(
            "Lead qualifie : %s (%s) — score %d",
            name,
            company.get("dept"),
            score_result["score"],
        )

        # Etape 5 : Notification Telegram
        if dry_run:
            logger.info("[DRY RUN] Notification non envoyee pour %s", name)
        else:
            try:
                notify_lead(lead)  # type: ignore[arg-type]
            except Exception as exc:
                logger.warning("telegram_notifier echoue pour %s: %s", name, exc)

    logger.info(
        "Orchestrateur termine : %d/%d leads qualifies",
        len(qualified),
        len(companies),
    )
    return qualified
