"""Tests for apps.leadcommercial.orchestrator."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

import apps.leadcommercial.orchestrator as orch


def _company(**overrides) -> dict:
    base = {
        "siren": "123456789",
        "siret": "12345678900001",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",
        "code_naf": "70.22Z",
        "dept": "75",
        "commune": "PARIS",
        "date_creation": "2026-04-01",
    }
    base.update(overrides)
    return base


def _score(**overrides) -> dict:
    base = {
        "siren": "123456789",
        "score": 80,
        "signal_type": "creation",
        "scoring_details": ["Signal creation: +100"],
        "qualified": True,
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }
    base.update(overrides)
    return base


def _enrichment(**overrides) -> dict:
    base = {
        "dirigeant_nom": "DUPONT",
        "dirigeant_prenom": "Jean",
        "dirigeant_email": "jean@test.com",
        "site_web": "https://test.com",
        "capital_social": 10000,
    }
    base.update(overrides)
    return base


def test_run_returns_empty_on_sirene_failure():
    with patch.object(
        orch, "fetch_idf_companies", side_effect=ValueError("SIRENE_API_TOKEN manquant")
    ):
        result = orch.run()
    assert result == []


def test_run_skips_low_score_leads():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(
            orch, "score_company", return_value=_score(score=30, qualified=False)
        ),
    ):
        result = orch.run(dry_run=True)
    assert result == []


def test_run_dry_run_skips_write_and_notify():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead") as mock_write,
        patch.object(orch, "notify_lead") as mock_notify,
    ):
        result = orch.run(dry_run=True)
    assert len(result) == 1
    mock_write.assert_not_called()
    mock_notify.assert_not_called()


def test_run_full_pipeline_calls_all_agents():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead", return_value=True) as mock_write,
        patch.object(orch, "notify_lead", return_value=True) as mock_notify,
        patch.object(orch, "fetch_icp", return_value=None),
        patch.dict(os.environ, {"CABINET_ID": "cab-123"}),
    ):
        result = orch.run(dry_run=False)
    assert len(result) == 1
    mock_write.assert_called_once()
    mock_notify.assert_called_once()


def test_run_lead_merges_company_score_enrichment():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead", return_value=True),
        patch.object(orch, "notify_lead", return_value=True),
    ):
        result = orch.run(dry_run=False)
    lead = result[0]
    assert lead["denomination"] == "TEST SAS"
    assert lead["score"] == 80
    assert lead["dirigeant_nom"] == "DUPONT"
    assert lead["capital_social"] == 10000


def test_run_skips_locked_lead():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead", return_value=False),
        patch.object(orch, "notify_lead") as mock_notify,
    ):
        result = orch.run(dry_run=False)
    assert result == []
    mock_notify.assert_not_called()


def test_run_continues_after_enrichment_failure():
    with (
        patch.object(orch, "fetch_idf_companies", return_value=[_company()]),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", side_effect=RuntimeError("pappers down")),
        patch.object(orch, "write_lead", return_value=True),
        patch.object(orch, "notify_lead", return_value=True),
    ):
        result = orch.run(dry_run=False)
    assert len(result) == 1
    assert result[0]["dirigeant_nom"] == ""


def test_run_continues_after_scorer_failure():
    two = [_company(siren="111"), _company(siren="222", denomination="OK SAS")]
    scores = [RuntimeError("scorer fail"), _score(score=80, siren="222")]

    def score_side_effect(params):
        val = scores.pop(0)
        if isinstance(val, Exception):
            raise val
        return val

    with (
        patch.object(orch, "fetch_idf_companies", return_value=two),
        patch.object(orch, "score_company", side_effect=score_side_effect),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead", return_value=True),
        patch.object(orch, "notify_lead", return_value=True),
    ):
        result = orch.run(dry_run=False)
    assert len(result) == 1
    assert result[0]["denomination"] == "OK SAS"


def test_run_icp_loaded_once_for_batch():
    three = [_company(siren=str(i)) for i in range(3)]
    with (
        patch.object(orch, "fetch_idf_companies", return_value=three),
        patch.object(orch, "score_company", return_value=_score(score=80)),
        patch.object(orch, "enrich_lead", return_value=_enrichment()),
        patch.object(orch, "write_lead", return_value=True),
        patch.object(orch, "notify_lead", return_value=True),
        patch.object(orch, "fetch_icp", return_value=None) as mock_icp,
        patch.dict(os.environ, {"CABINET_ID": "cab-123"}),
    ):
        result = orch.run(dry_run=False)
    mock_icp.assert_called_once()
    assert len(result) == 3
