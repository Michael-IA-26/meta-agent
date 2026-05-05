import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.leadcommercial.sirene_client import DEPT_IDF, build_query, parse_company


def test_dept_idf():
    assert "75" in DEPT_IDF
    assert "92" in DEPT_IDF
    assert "69" not in DEPT_IDF
    print("OK: test_dept_idf")


def test_build_query():
    query = build_query()
    assert "dateCreationEtablissement" in query
    assert "etablissementSiege:true" in query
    assert "75" in query
    print("OK: test_build_query")


def test_parse_company():
    fake = {
        "siren": "123456789",
        "siret": "12345678900012",
        "uniteLegale": {
            "denominationUniteLegale": "TEST SAS",
            "categorieJuridiqueUniteLegale": "5710",
        },
        "adresseEtablissement": {
            "codePostalEtablissement": "75001",
            "libelleCommuneEtablissement": "PARIS 1",
        },
        "activitePrincipaleEtablissement": "62.01Z",
        "dateCreationEtablissement": "2026-05-05",
    }
    r = parse_company(fake)
    assert r["siren"] == "123456789"
    assert r["denomination"] == "TEST SAS"
    assert r["dept"] == "75"
    assert r["code_naf"] == "62.01Z"
    print("OK: test_parse_company")


def test_parse_sans_denomination():
    fake = {
        "siren": "987654321",
        "siret": "98765432100001",
        "uniteLegale": {
            "prenomUsuelUniteLegale": "Jean",
            "nomUniteLegale": "DUPONT",
            "categorieJuridiqueUniteLegale": "5499",
        },
        "adresseEtablissement": {
            "codePostalEtablissement": "92100",
            "libelleCommuneEtablissement": "BOULOGNE",
        },
        "activitePrincipaleEtablissement": "56.10A",
        "dateCreationEtablissement": "2026-05-05",
    }
    r = parse_company(fake)
    assert r["denomination"] == "Jean DUPONT"
    assert r["dept"] == "92"
    print("OK: test_parse_sans_denomination")


if __name__ == "__main__":
    test_dept_idf()
    test_build_query()
    test_parse_company()
    test_parse_sans_denomination()
    print()
    print("4/4 tests passes !")
