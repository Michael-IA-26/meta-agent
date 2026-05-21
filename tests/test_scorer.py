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


def test_scored_lead_enrichment_defaults():
    company = {
        "siren": "444555666",
        "denomination": "NOUVEAU TRAITEUR SAS",
        "forme_juridique": "5710",
        "code_naf": "56.21Z",
        "dept": "78",
        "date_creation": "2026-04-01",
    }
    result = score_lead(company, "creation")
    assert result["dirigeant_nom"] == ""
    assert result["dirigeant_prenom"] == ""
    assert result["dirigeant_email"] == ""
    assert result["site_web"] == ""
    assert result["capital_social"] is None
    print("OK: test_scored_lead_enrichment_defaults")


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


def _base_icp(**overrides) -> dict:
    base: dict = {
        "secteurs": [],
        "zone_deps": [],
        "forme_juridique": [],
        "signaux_prioritaires": [],
        "signaux_exclus": [],
        "scoring_rules": {},
    }
    base.update(overrides)
    return base


def test_icp_secteurs_override_naf():
    """ICP secteurs replaces NAF_RESTAURATION; company in ICP sectors gets +10."""
    company = {
        "siren": "555666777",
        "denomination": "INFORMATIQUE SAS",
        "forme_juridique": "5710",
        "code_naf": "62.01Z",  # not in default NAF_RESTAURATION
        "dept": "75",
        "date_creation": "2026-04-01",
    }
    icp = _base_icp(secteurs=["62.01Z", "62.02A"])
    result = score_lead(company, "creation", icp=icp)
    assert result["score"] == 100
    assert any("ICP" in d for d in result["scoring_details"])


def test_icp_zone_deps_override_idf():
    """ICP zone_deps accepts departments outside default IDF."""
    company = {
        "siren": "666777888",
        "denomination": "MARSEILLE SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "13",  # Bouches-du-Rhone, hors IDF par defaut
        "date_creation": "2026-04-01",
    }
    icp = _base_icp(zone_deps=["13", "06", "83"])
    result = score_lead(company, "creation", icp=icp)
    assert result["score"] > 0
    assert result["qualified"] is True


def test_icp_signal_exclu_score_zero():
    """Signal listed in signaux_exclus must immediately return score=0."""
    company = {
        "siren": "777888999",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "dept": "75",
        "date_creation": "2026-04-01",
    }
    icp = _base_icp(signaux_exclus=["intention", "rattrapage"])
    result = score_lead(company, "intention", icp=icp)
    assert result["score"] == 0
    assert result["qualified"] is False
    assert "exclu" in result["scoring_details"][0]


def test_icp_scoring_rules_override_base():
    """scoring_rules JSONB overrides the default base score for a signal."""
    company = {
        "siren": "888999000",
        "denomination": "OVERRIDE SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "92",
        "date_creation": "2026-04-01",
    }
    icp = _base_icp(scoring_rules={"creation": 70})
    result = score_lead(company, "creation", icp=icp)
    assert result["score"] == 70
    assert any("ICP override" in d for d in result["scoring_details"])


def test_icp_signal_prioritaire_bonus():
    """Signal in signaux_prioritaires gets +5 on top of base score."""
    company = {
        "siren": "999000111",
        "denomination": "PRIO SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "75",
        "date_creation": "2026-04-01",
    }
    icp = _base_icp(signaux_prioritaires=["rattrapage"])
    result = score_lead(company, "rattrapage", icp=icp)
    # base 80 + priority +5 = 85
    assert result["score"] == 85
    assert any("prioritaire ICP" in d for d in result["scoring_details"])


if __name__ == "__main__":
    test_signal_creation()
    test_hors_idf_score_zero()
    test_bonus_restauration()
    test_signal_rattrapage()
    test_scored_lead_enrichment_defaults()
    test_score_batch()
    test_icp_secteurs_override_naf()
    test_icp_zone_deps_override_idf()
    test_icp_signal_exclu_score_zero()
    test_icp_scoring_rules_override_base()
    test_icp_signal_prioritaire_bonus()
    print()
    print("11/11 tests passes !")
