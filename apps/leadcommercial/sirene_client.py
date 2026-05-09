import os
from datetime import datetime, timedelta

import httpx

SIRENE_TOKEN = os.getenv("SIRENE_API_TOKEN", "")
SIRENE_BASE_URL = "https://api.insee.fr/api-sirene/3.11"

DEPT_IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
FORMES_JURIDIQUES = ["5710", "5720", "5499"]  # SAS, SASU, EURL


def get_headers() -> dict:
    return {
        "X-INSEE-Api-Key-Integration": SIRENE_TOKEN,
        "Accept": "application/json",
    }


def build_query() -> str:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return f"dateCreationEtablissement:{yesterday} AND etablissementSiege:true"


def fetch_new_companies(max_results: int = 20) -> list[dict]:
    query = build_query()
    params = {
        "q": query,
        "nombre": max_results,
        "champs": (
            "siret,siren,denominationUniteLegale,"
            "activitePrincipaleEtablissement,prenomUsuelUniteLegale,nomUniteLegale,nomUsageUniteLegale,"
            "codePostalEtablissement,libelleCommuneEtablissement,"
            "dateCreationEtablissement,categorieJuridiqueUniteLegale"
        ),
    }
    response = httpx.get(
        f"{SIRENE_BASE_URL}/siret",
        headers=get_headers(),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    etablissements = data.get("etablissements", [])
    print(f"Entreprises trouvees : {len(etablissements)}")
    return etablissements


def parse_company(etab: dict) -> dict:
    ul = etab.get("uniteLegale", {})
    adresse = etab.get("adresseEtablissement", {})
    return {
        "siren": etab.get("siren"),
        "siret": etab.get("siret"),
        "denomination": ul.get("denominationUniteLegale")
        or (
            f"{ul.get('prenomUsuelUniteLegale') or ''} {ul.get('nomUsageUniteLegale') or ul.get('nomUniteLegale') or ''}".strip()
        )
        or (
            f"{ul.get('prenomUsuelUniteLegale', '')} "
            f"{ul.get('nomUniteLegale', '')}".strip()
        ),
        "forme_juridique": ul.get("categorieJuridiqueUniteLegale"),
        "code_naf": ul.get("activitePrincipaleUniteLegale"),
        "dept": adresse.get("codePostalEtablissement", "")[:2],
        "commune": adresse.get("libelleCommuneEtablissement"),
        "date_creation": etab.get("dateCreationEtablissement"),
    }


if __name__ == "__main__":
    print("Test Sirene API...")
    if not SIRENE_TOKEN:
        print("SIRENE_API_TOKEN manquant — configure Doppler")
    else:
        companies = fetch_new_companies(max_results=5)
        for c in companies:
            parsed = parse_company(c)
            print(parsed)
