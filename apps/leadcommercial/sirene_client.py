import logging
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

SIRENE_TOKEN = os.getenv("SIRENE_API_TOKEN", "")
SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11"

DEPT_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
FORMES_JURIDIQUES = ["5710", "5720", "5499"]  # SAS, SASU, EURL

CHAMPS = ",".join(
    [
        "siret",
        "siren",
        "denominationUniteLegale",
        "prenomUsuelUniteLegale",
        "nomUniteLegale",
        "nomUsageUniteLegale",
        "activitePrincipaleUniteLegale",
        "categorieJuridiqueUniteLegale",
        "codePostalEtablissement",
        "libelleCommuneEtablissement",
        "dateCreationEtablissement",
    ]
)


def get_headers() -> dict:
    return {
        "X-INSEE-Api-Key-Integration": SIRENE_TOKEN,
        "Accept": "application/json",
    }


def build_query(date: str | None = None) -> str:
    target_date = date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return f"dateCreationEtablissement:{target_date} AND etablissementSiege:true"


def fetch_new_companies(max_results: int = 20, date: str | None = None) -> list[dict]:
    if not SIRENE_TOKEN:
        raise ValueError("SIRENE_API_TOKEN manquant — configure Doppler")

    query = build_query(date)
    params = {"q": query, "nombre": str(max_results), "champs": CHAMPS}
    proxies = os.getenv("FIXIE_URL")

    try:
        response = httpx.get(
            f"{SIRENE_BASE_URL}/siret",
            headers=get_headers(),
            params=params,
            timeout=30,
            proxy=proxies,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.error(
            f"Erreur API Sirene {e.response.status_code}: {e.response.text[:200]}"
        )
        raise

    data = response.json()
    etablissements = data.get("etablissements", [])
    logger.info(f"Sirene: {len(etablissements)} etablissements recus")
    return etablissements


def _get_denomination(ul: dict) -> str:
    if ul.get("denominationUniteLegale"):
        return ul["denominationUniteLegale"]
    prenom = ul.get("prenomUsuelUniteLegale") or ""
    nom = ul.get("nomUsageUniteLegale") or ul.get("nomUniteLegale") or ""
    return f"{prenom} {nom}".strip()


def parse_company(etab: dict) -> dict:
    ul = etab.get("uniteLegale", {})
    adresse = etab.get("adresseEtablissement", {})
    code_postal = adresse.get("codePostalEtablissement") or ""

    # Exclure les données non diffusibles
    if code_postal.startswith("["):
        code_postal = ""

    dept = code_postal[:2] if code_postal else ""

    return {
        "siren": etab.get("siren"),
        "siret": etab.get("siret"),
        "denomination": _get_denomination(ul),
        "forme_juridique": ul.get("categorieJuridiqueUniteLegale"),
        "code_naf": ul.get("activitePrincipaleUniteLegale"),
        "dept": dept,
        "commune": adresse.get("libelleCommuneEtablissement"),
        "date_creation": etab.get("dateCreationEtablissement"),
    }


def fetch_and_parse_idf(max_results: int = 100, date: str | None = None) -> list[dict]:
    etablissements = fetch_new_companies(max_results=max_results, date=date)
    companies = [parse_company(e) for e in etablissements]
    idf = [c for c in companies if c["dept"] in DEPT_IDF]
    logger.info(f"Sirene: {len(idf)}/{len(companies)} etablissements en IDF")
    return idf
