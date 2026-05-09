import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.leadcommercial.sirene_client import (
    DEPT_IDF,
    _get_denomination,
    build_query,
    parse_company,
)


def test_dept_idf():
    assert "75" in DEPT_IDF
    assert "92" in DEPT_IDF
    assert "69" not in DEPT_IDF
    print("OK: test_dept_idf")


def test_build_query():
    query = build_query()
    assert "dateCreationEtablissement" in query
    assert "etablissementSiege:true" in query
    print("OK: test_build_query")


def test_build_query_with_date():
    query = build_query(date="2026-05-01")
    assert "2026-05-01" in query
    print("OK: test_build_query_with_date")


def test_get_denomination_societe():
    ul = {"denominationUniteLegale": "ACME SAS"}
    assert _get_denomination(ul) == "ACME SAS"
    print("OK: test_get_denomination_societe")


def test_get_denomination_personne():
    ul = {
        "denominationUniteLegale": None,
        "prenomUsuelUniteLegale": "Jean",
        "nomUsageUniteLegale": "DUPONT",
        "nomUniteLegale": "DURAND",
    }
    assert _get_denomination(ul) == "Jean DUPONT"
    print("OK: test_get_denomination_personne")


def test_parse_company_idf():
    fake = {
        "siren": "123456789",
        "siret": "12345678900012",
        "uniteLegale": {
            "denominationUniteLegale": "TEST SAS",
            "categorieJuridiqueUniteLegale": "5710",
            "activitePrincipaleUniteLegale": "62.01Z",
            "prenomUsuelUniteLegale": None,
            "nomUniteLegale": None,
            "nomUsageUniteLegale": None,
        },
        "adresseEtablissement": {
            "codePostalEtablissement": "75001",
            "libelleCommuneEtablissement": "PARIS 1",
        },
        "dateCreationEtablissement": "2026-05-09",
    }
    r = parse_company(fake)
    assert r["siren"] == "123456789"
    assert r["denomination"] == "TEST SAS"
    assert r["dept"] == "75"
    assert r["code_naf"] == "62.01Z"
    print("OK: test_parse_company_idf")


def test_parse_company_non_diffusible():
    fake = {
        "siren": "999999999",
        "siret": "99999999900001",
        "uniteLegale": {
            "denominationUniteLegale": "[ND]",
            "categorieJuridiqueUniteLegale": "5710",
            "activitePrincipaleUniteLegale": None,
            "prenomUsuelUniteLegale": None,
            "nomUniteLegale": None,
            "nomUsageUniteLegale": None,
        },
        "adresseEtablissement": {
            "codePostalEtablissement": "[ND]",
            "libelleCommuneEtablissement": "[ND]",
        },
        "dateCreationEtablissement": "2026-05-09",
    }
    r = parse_company(fake)
    assert r["dept"] == ""
    print("OK: test_parse_company_non_diffusible")


if __name__ == "__main__":
    test_dept_idf()
    test_build_query()
    test_build_query_with_date()
    test_get_denomination_societe()
    test_get_denomination_personne()
    test_parse_company_idf()
    test_parse_company_non_diffusible()
    print()
    print("7/7 tests passes !")
