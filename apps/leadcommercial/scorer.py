import logging
from datetime import date, datetime
from typing import Any, TypedDict

logger = logging.getLogger(__name__)

SCORING_RULES = {
    "creation": 100,
    "rattrapage": 80,
    "fiscal": 80,
    "intention": 60,
}

DEPT_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]

FORMES_PRIORITAIRES = ["5710", "5720", "5499"]  # SAS, SASU, EURL

NAF_RESTAURATION = ["56.10A", "56.10B", "56.21Z", "56.29A", "56.29B", "56.30Z"]


class IcpContext(TypedDict):
    """ICP settings loaded from the icps Supabase table for a given cabinet."""

    secteurs: list[str]
    zone_deps: list[str]
    forme_juridique: list[str]
    signaux_prioritaires: list[str]
    signaux_exclus: list[str]
    scoring_rules: dict[str, Any]


class ScoredLead(TypedDict):
    siren: str | None
    score: int
    signal_type: str
    scoring_details: list[str]
    qualified: bool
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def score_lead(
    company: dict,
    signal_type: str = "creation",
    icp: IcpContext | None = None,
) -> ScoredLead:
    """Score a company lead, optionally adjusting rules from a Supabase ICP."""
    score = 0
    details: list[str] = []

    # Unpack ICP fields — fallback to empty defaults when no ICP provided
    signaux_exclus: list[str] = icp["signaux_exclus"] if icp else []
    signaux_prioritaires: list[str] = icp["signaux_prioritaires"] if icp else []
    icp_secteurs: list[str] = icp["secteurs"] if icp else []
    icp_zones: list[str] = icp["zone_deps"] if icp else []
    icp_formes: list[str] = icp["forme_juridique"] if icp else []
    scoring_rules: dict[str, Any] = icp["scoring_rules"] if icp else {}

    # 1. Signal exclu par l'ICP — retour immediat avant tout scoring
    if signal_type in signaux_exclus:
        return {
            "siren": company.get("siren"),
            "score": 0,
            "signal_type": signal_type,
            "scoring_details": [f"Signal {signal_type} exclu par ICP: score = 0"],
            "qualified": False,
            "dirigeant_nom": "",
            "dirigeant_prenom": "",
            "dirigeant_email": "",
            "site_web": "",
            "capital_social": None,
        }

    # 2. Score de base — scoring_rules ICP override si disponible
    if signal_type in scoring_rules:
        base_score = int(scoring_rules[signal_type])
        details.append(f"Signal {signal_type} (ICP override): +{base_score}")
    else:
        base_score = SCORING_RULES.get(signal_type, 0)
        details.append(f"Signal {signal_type}: +{base_score}")
    score += base_score

    # 3. Bonus signal prioritaire ICP (+5 si explicitement liste)
    if signaux_prioritaires and signal_type in signaux_prioritaires:
        score = min(score + 5, 100)
        details.append("Signal prioritaire ICP: +5")

    # 4. Bonus secteur — ICP.secteurs si non vide, sinon NAF_RESTAURATION
    priority_sectors = icp_secteurs or NAF_RESTAURATION
    is_icp_sector = bool(icp_secteurs)
    code_naf = company.get("code_naf", "")
    if code_naf in priority_sectors:
        score = min(score + 10, 100)
        details.append(
            "Secteur prioritaire (ICP): +10"
            if is_icp_sector
            else "Secteur restauration (prioritaire): +10"
        )

    # 5. Bonus creation tres recente (< 7 jours)
    date_creation = company.get("date_creation")
    if date_creation:
        try:
            if isinstance(date_creation, str):
                d = datetime.strptime(date_creation, "%Y-%m-%d").date()
            else:
                d = date_creation
            age_days = (date.today() - d).days
            if age_days <= 7:
                score = min(score + 10, 100)
                details.append(f"Creation tres recente ({age_days}j): +10")
            elif age_days <= 14:
                score = min(score + 5, 100)
                details.append(f"Creation recente ({age_days}j): +5")
        except ValueError:
            pass

    # 6. Malus forme juridique — ICP.forme_juridique si non vide, sinon FORMES_PRIORITAIRES
    priority_formes = icp_formes or FORMES_PRIORITAIRES
    forme = company.get("forme_juridique", "")
    if forme and forme not in priority_formes:
        score = max(score - 10, 0)
        details.append(f"Forme juridique non prioritaire ({forme}): -10")

    # 7. Filtre zone geographique — ICP.zone_deps si non vide, sinon DEPT_IDF
    priority_zones = icp_zones or DEPT_IDF
    is_icp_zone = bool(icp_zones)
    dept = company.get("dept", "")
    if dept not in priority_zones:
        score = 0
        details.append(
            f"Hors zone ICP ({dept}): score = 0"
            if is_icp_zone
            else f"Hors IDF ({dept}): score = 0"
        )

    return {
        "siren": company.get("siren"),
        "score": score,
        "signal_type": signal_type,
        "scoring_details": details,
        "qualified": score >= 50,
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }


def score_batch(
    companies: list,
    signal_type: str = "creation",
    icp: IcpContext | None = None,
) -> list[ScoredLead]:
    results = []
    for company in companies:
        result = score_lead(company, signal_type, icp=icp)
        results.append(result)
        status = "QUALIFIE" if result["qualified"] else "rejete"
        logger.info(
            f"  {company.get('denomination', 'N/A')} — score {result['score']} — {status}"
        )
    return results
