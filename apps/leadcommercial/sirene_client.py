import logging
import os
import threading
import time
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

SIRENE_TOKEN = os.getenv("SIRENE_API_TOKEN", "")
SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11"

# Plan public INSEE : 30 req/min → 1 req toutes les 2 secondes minimum.
_rate_lock = threading.Lock()
_last_call_time: float = 0.0
_MIN_INTERVAL = 2.0

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
        "trancheEffectifsUniteLegale",
    ]
)


def _throttle() -> None:
    global _last_call_time
    with _rate_lock:
        elapsed = time.monotonic() - _last_call_time
        wait = _MIN_INTERVAL - elapsed
        if wait > 0:
            time.sleep(wait)
        _last_call_time = time.monotonic()


def get_headers() -> dict:
    return {
        "X-INSEE-Api-Key-Integration": SIRENE_TOKEN,
        "Accept": "application/json",
    }


def build_query(
    date: str | None = None,
    code_postal: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> str:
    if date_from:
        _to = date_to or datetime.now().strftime("%Y-%m-%d")
        date_part = f"dateCreationEtablissement:[{date_from} TO {_to}]"
    else:
        target_date = date or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_part = f"dateCreationEtablissement:{target_date}"

    query = f"{date_part} AND etablissementSiege:true"
    if code_postal:
        query += f" AND codePostalEtablissement:{code_postal}"
    return query


def fetch_new_companies(
    max_results: int = 20,
    date: str | None = None,
    code_postal: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    if not SIRENE_TOKEN:
        raise ValueError("SIRENE_API_TOKEN manquant — configure Doppler")

    _throttle()

    query = build_query(date=date, code_postal=code_postal, date_from=date_from, date_to=date_to)
    params = {"q": query, "nombre": str(max_results), "champs": CHAMPS}

    try:
        response = httpx.get(
            f"{SIRENE_BASE_URL}/siret",
            headers=get_headers(),
            params=params,
            timeout=30,
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
        "code_postal": code_postal,
        "dept": dept,
        "commune": adresse.get("libelleCommuneEtablissement"),
        "date_creation": etab.get("dateCreationEtablissement"),
        "effectif": ul.get("trancheEffectifsUniteLegale") or "",
    }


def fetch_and_parse_idf(
    max_results: int = 100,
    date: str | None = None,
    code_postal: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    etablissements = fetch_new_companies(
        max_results=max_results,
        date=date,
        code_postal=code_postal,
        date_from=date_from,
        date_to=date_to,
    )
    companies = [parse_company(e) for e in etablissements]
    if code_postal:
        # Already filtered at API level; still log
        logger.info(f"Sirene: {len(companies)} etablissements pour CP {code_postal}")
        return companies
    idf = [c for c in companies if c["dept"] in DEPT_IDF]
    logger.info(f"Sirene: {len(idf)}/{len(companies)} etablissements en IDF")
    return idf
