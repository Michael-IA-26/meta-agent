"""Orchestrateur LeadCommercial.

Enchaîne les 5 agents spécialisés sans logique métier :
sirene_fetcher → lead_scorer → pappers_enricher → dropcontact → supabase_writer → telegram_notifier.
"""

import logging
import os
from typing import TypedDict

from apps.leadcommercial.agents.lead_scorer import ScoreInput, score_company
from apps.leadcommercial.agents.pappers_enricher import EnrichInput, enrich_lead
from apps.leadcommercial.agents.sirene_fetcher import SireneInput, fetch_idf_companies
from apps.leadcommercial.agents.supabase_writer import write_lead
from apps.leadcommercial.agents.telegram_notifier import notify_lead
from apps.leadcommercial.config import LeadHunterConfig, date_from_config, load_config
from apps.leadcommercial.config.schema import SeuilsScoring
from apps.leadcommercial.dropcontact_client import fetch_email
from apps.leadcommercial.supabase_client import fetch_icp

logger = logging.getLogger(__name__)

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
    code_postal: str
    dept: str
    commune: str | None
    date_creation: str | None
    effectif: str
    score: int
    signal_type: str
    scoring_details: list[str]
    qualified: bool
    statut: str
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def _get_statut(score: int, scoring: SeuilsScoring) -> str:
    if score >= scoring.chaud_min:
        return "CHAUD"
    if score >= scoring.tiede_min:
        return "TIEDE"
    return "EXCLU"


def _passes_filters(company: dict, cfg: LeadHunterConfig) -> bool:
    """Applique les post-filtres ICP (NAF, effectif, formes juridiques, codes postaux)."""
    r = cfg.recherche

    # Filtre codes_postaux (utile si plusieurs codes ou si la requête Sirene était large)
    if len(r.codes_postaux) > 1:
        if company.get("code_postal") not in r.codes_postaux:
            return False

    # Filtre NAF exclus
    if r.naf_exclus and company.get("code_naf") in r.naf_exclus:
        return False

    # Filtre effectif
    effectif_tranches = r.effectif_tranches()
    if effectif_tranches:  # liste vide = pas de filtre
        if company.get("effectif", "") not in effectif_tranches:
            return False

    # Filtre formes juridiques incluses (liste blanche)
    if r.formes_juridiques_incluses:
        if company.get("forme_juridique") not in r.formes_juridiques_incluses:
            return False

    # Filtre formes juridiques exclues (liste noire)
    if r.formes_juridiques_exclues:
        if company.get("forme_juridique") in r.formes_juridiques_exclues:
            return False

    return True


def run(
    cfg: LeadHunterConfig | None = None,
    dry_run: bool = False,
    max_leads: int | None = None,
    max_enrichments: int | None = None,
) -> list[LeadEnriched]:
    """Run the full LeadCommercial pipeline.

    Chain of agents:
    1. sirene_fetcher     — fetch companies (codes_postaux + fenêtre dates du cfg)
    2. post-filtres       — NAF, effectif, formes juridiques
    3. lead_scorer        — score chaque entreprise
    4. pappers_enricher   — enrichit les leads CHAUD (dirigeant nom/prénom/capital)
    5. dropcontact        — trouve l'email des leads CHAUD (plafonné à max_enrichments)
    6. supabase_writer    — persiste et verrouille (ignore les SIRENs déjà lockés)
    7. telegram_notifier  — alerte Telegram pour chaque lead persisté

    dry_run=True saute les étapes 6 et 7.
    max_leads plafonne le nombre de leads qualifiés traités.
    max_enrichments plafonne les appels Dropcontact (CHAUD seulement).
    """
    if cfg is None:
        cfg = load_config()

    logger.info("Orchestrateur LeadCommercial — demarrage")

    scoring = cfg.scoring
    r = cfg.recherche

    # Résolution de la fenêtre de dates à partir du config
    date_from, date_to = date_from_config(cfg)

    # Pour la requête Sirene : un seul code postal si un seul, sinon fetch large IDF
    code_postal_query = r.codes_postaux[0] if len(r.codes_postaux) == 1 else None

    # Setup: charger l'ICP une seule fois pour tout le batch
    icp = None
    cabinet_id = os.getenv("CABINET_ID", "")
    if not dry_run and cabinet_id:
        icp = fetch_icp(cabinet_id)
        if icp:
            logger.info("ICP charge pour cabinet %s...", cabinet_id[:8])
        else:
            logger.warning("ICP absent — scoring avec regles par defaut")

    # Etape 1 : Sirene → liste entreprises
    sirene_max = (max_leads or 10) * 10  # sur-fetch pour avoir assez après filtrage
    try:
        companies = fetch_idf_companies(
            SireneInput(
                max_results=min(sirene_max, 500),
                date=None,
                code_postal=code_postal_query,
                date_from=date_from,
                date_to=date_to,
            )
        )
    except Exception as exc:
        logger.error("sirene_fetcher echoue: %s", exc, exc_info=True)
        return []
    logger.info("Orchestrateur: %d entreprises recues de Sirene", len(companies))

    # Etape 2 : Post-filtres ICP (NAF, effectif, formes, codes postaux multiples)
    before_filter = len(companies)
    companies = [c for c in companies if _passes_filters(c, cfg)]
    logger.info(
        "Post-filtres: %d/%d entreprises retenues (NAF, effectif, formes)",
        len(companies),
        before_filter,
    )

    qualified: list[LeadEnriched] = []
    enrichments_done = 0

    for company in companies:
        if max_leads is not None and len(qualified) >= max_leads:
            logger.info("Limite max_leads=%d atteinte — arret", max_leads)
            break

        name = company.get("denomination", "N/A")
        siren = company.get("siren") or ""

        # Etape 3 : Score
        try:
            score_result = score_company(
                ScoreInput(company=company, signal_type="creation", icp=icp)
            )
        except Exception as exc:
            logger.error("lead_scorer echoue pour %s: %s", name, exc)
            continue

        if score_result["score"] < scoring.tiede_min:
            continue

        statut = _get_statut(score_result["score"], scoring)

        # Etape 4 : Enrichissement Pappers (CHAUD uniquement)
        enrichment = dict(_EMPTY_ENRICHMENT)
        if statut == "CHAUD":
            try:
                pappers = enrich_lead(EnrichInput(siren=siren))
                enrichment.update(pappers)
            except Exception as exc:
                logger.warning("pappers_enricher echoue pour %s: %s", name, exc)

        # Etape 5 : Email Dropcontact (CHAUD uniquement, plafond max_enrichments)
        dc_email = ""
        if statut == "CHAUD":
            cap = max_enrichments if max_enrichments is not None else 5
            if enrichments_done < cap:
                try:
                    dc = fetch_email(
                        first_name=enrichment.get("dirigeant_prenom", ""),
                        last_name=enrichment.get("dirigeant_nom", ""),
                        company=name,
                        siren=siren or None,
                    )
                    dc_email = dc["email"]
                    enrichments_done += 1
                    logger.info(
                        "Dropcontact (%d/%d): %s → %s",
                        enrichments_done,
                        cap,
                        name,
                        dc_email or "(vide)",
                    )
                except Exception as exc:
                    logger.warning("dropcontact echoue pour %s: %s", name, exc)
            else:
                logger.info("Plafond Dropcontact atteint (%d) — skip pour %s", cap, name)

        if dc_email:
            enrichment["dirigeant_email"] = dc_email

        lead: LeadEnriched = {
            **company,  # type: ignore[misc]
            **score_result,
            **enrichment,
            "statut": statut,
            "qualified": score_result["score"] >= scoring.tiede_min,
            "code_postal": company.get("code_postal", ""),
            "effectif": company.get("effectif", ""),
        }

        # Etape 6 : Persistance Supabase
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
            "Lead %s : %s (%s) — score %d",
            statut,
            name,
            company.get("code_postal") or company.get("dept"),
            score_result["score"],
        )

        # Etape 7 : Notification Telegram
        if dry_run:
            logger.info("[DRY RUN] Notification non envoyee pour %s", name)
        else:
            try:
                notify_lead(lead)  # type: ignore[arg-type]
            except Exception as exc:
                logger.warning("telegram_notifier echoue pour %s: %s", name, exc)

    logger.info(
        "Orchestrateur termine : %d/%d leads qualifies (%d enrichissements Dropcontact)",
        len(qualified),
        len(companies),
        enrichments_done,
    )
    return qualified


def print_leads_report(leads: list[LeadEnriched]) -> None:
    """Affiche un rapport console lisible pour chaque lead du batch."""
    sep = "─" * 70
    chaud = [ld for ld in leads if ld["statut"] == "CHAUD"]
    tiede = [ld for ld in leads if ld["statut"] == "TIEDE"]

    print(f"\n{'═' * 70}")
    print(f"  RAPPORT BATCH LEAD HUNTER — {len(leads)} leads qualifiés")
    print(f"  CHAUD: {len(chaud)}  TIÈDE: {len(tiede)}")
    print(f"{'═' * 70}\n")

    for i, lead in enumerate(leads, 1):
        statut = lead["statut"]
        label = f"🔥 {statut}" if statut == "CHAUD" else f"🌡  {statut}"
        print(f"[{i:02d}] {label}  —  score {lead['score']}/100")
        print(sep)
        print(f"  Raison sociale : {lead['denomination'] or '—'}")
        print(f"  SIREN          : {lead['siren'] or '—'}")
        print(f"  NAF            : {lead['code_naf'] or '—'}")
        print(f"  Forme juridique: {lead['forme_juridique'] or '—'}")
        print(f"  Code postal    : {lead['code_postal'] or lead['dept'] or '—'}")
        print(f"  Date création  : {lead['date_creation'] or '—'}")
        print(f"  Effectif tranche: {lead['effectif'] or 'non renseigné'}")
        print(f"  Scoring        : {', '.join(lead['scoring_details'])}")
        if statut == "CHAUD":
            nom = f"{lead['dirigeant_prenom']} {lead['dirigeant_nom']}".strip()
            print(f"  Dirigeant      : {nom or '— (non trouvé Pappers)'}")
            print(f"  Email          : {lead['dirigeant_email'] or '— (non trouvé Dropcontact)'}")
            if lead['site_web']:
                print(f"  Site web       : {lead['site_web']}")
            if lead['capital_social']:
                print(f"  Capital social : {lead['capital_social']} €")
        print()
