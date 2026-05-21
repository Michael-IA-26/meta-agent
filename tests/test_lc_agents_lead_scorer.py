"""Tests for apps.leadcommercial.agents.lead_scorer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.agents.lead_scorer import ScoreInput, score_company


def _company(**overrides) -> dict:
    base = {
        "siren": "123456789",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "75",
        "date_creation": "2026-04-01",
    }
    base.update(overrides)
    return base


def test_score_company_qualified():
    result = score_company(
        ScoreInput(company=_company(), signal_type="creation", icp=None)
    )
    assert result["score"] == 100
    assert result["qualified"] is True


def test_score_company_hors_idf_score_zero():
    result = score_company(
        ScoreInput(company=_company(dept="69"), signal_type="creation", icp=None)
    )
    assert result["score"] == 0
    assert result["qualified"] is False


def test_score_company_returns_empty_enrichment_placeholders():
    result = score_company(
        ScoreInput(company=_company(), signal_type="creation", icp=None)
    )
    assert result["dirigeant_nom"] == ""
    assert result["dirigeant_prenom"] == ""
    assert result["dirigeant_email"] == ""
    assert result["site_web"] == ""
    assert result["capital_social"] is None


def test_score_company_delegates_to_scorer():
    fake = {
        "siren": "123456789",
        "score": 90,
        "signal_type": "rattrapage",
        "scoring_details": ["Signal rattrapage: +80"],
        "qualified": True,
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }
    with patch(
        "apps.leadcommercial.agents.lead_scorer.score_lead",
        return_value=fake,
    ) as mock:
        result = score_company(
            ScoreInput(company=_company(), signal_type="rattrapage", icp=None)
        )
    mock.assert_called_once_with(_company(), "rattrapage", icp=None)
    assert result == fake


def test_score_company_with_icp():
    icp = {
        "secteurs": ["70.22Z"],
        "zone_deps": ["75"],
        "forme_juridique": ["5710"],
        "signaux_prioritaires": [],
        "signaux_exclus": [],
        "scoring_rules": {},
    }
    result = score_company(
        ScoreInput(company=_company(), signal_type="creation", icp=icp)
    )
    assert result["score"] > 0
