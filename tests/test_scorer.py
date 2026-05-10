import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from apps.leadcommercial.scorer import score_batch, score_lead


def test_signal_creation():
    company = {
        "siren": "123456789",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "75",
        "date_creation": "2026-04-01",
    }
    result = score_lead(company, "creation")
    assert result["score"] == 100
    assert result["qualified"] is True
    print("OK: test_signal_creation")


def test_hors_idf_score_zero():
    company = {
        "siren": "111222333",
        "denomination": "LYON SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "69",
        "date_creation": "2026-05-01",
    }
    result = score_lead(company, "creation")
    assert result["score"] == 0
    assert result["qualified"] is False
    print("OK: test_hors_idf_score_zero")


def test_bonus_restauration():
    company = {
        "siren": "222333444",
        "denomination": "LE BON RESTO",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "dept": "92",
        "date_creation": datetime.now().strftime("%Y-%m-%d"),
    }
    result = score_lead(company, "creation")
    assert result["score"] == 100
    assert "restauration" in " ".join(result["scoring_details"]).lower()
    print("OK: test_bonus_restauration")


def test_signal_rattrapage():
    company = {
        "siren": "333444555",
        "denomination": "RETARD COMPTA SARL",
        "forme_juridique": "5499",
        "code_naf": "70.22Z",
        "dept": "93",
        "date_creation": "2026-01-01",
    }
    result = score_lead(company, "rattrapage")
    assert result["score"] == 80
    assert result["qualified"] is True
    print("OK: test_signal_rattrapage")


def test_score_batch():
    companies = [
        {
            "siren": "111",
            "denomination": "A",
            "forme_juridique": "5710",
            "code_naf": "70.22Z",
            "dept": "75",
            "date_creation": "2026-04-01",
        },
        {
            "siren": "222",
            "denomination": "B",
            "forme_juridique": "5710",
            "code_naf": "70.22Z",
            "dept": "69",
            "date_creation": "2026-04-01",
        },
    ]
    results = score_batch(companies, "creation")
    assert len(results) == 2
    assert results[0]["qualified"] is True
    assert results[1]["qualified"] is False
    print("OK: test_score_batch")


if __name__ == "__main__":
    test_signal_creation()
    test_hors_idf_score_zero()
    test_bonus_restauration()
    test_signal_rattrapage()
    test_score_batch()
    print()
    print("5/5 tests passes !")
