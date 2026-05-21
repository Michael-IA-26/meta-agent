import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.pipeline import (
    format_lead_alert,
    run_pipeline,
    send_telegram_alert,
)


def _base_score_result(**overrides) -> dict:
    base = {
        "score": 100,
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


def test_format_lead_alert():
    company = {
        "denomination": "TEST SAS",
        "commune": "PARIS",
        "dept": "75",
        "code_naf": "62.01Z",
        "date_creation": "2026-05-09",
        "siren": "123456789",
    }
    msg = format_lead_alert(company, _base_score_result())
    assert "TEST SAS" in msg
    assert "PARIS" in msg
    assert "100/100" in msg
    assert "123456789" in msg
    print("OK: test_format_lead_alert")


def test_format_lead_alert_with_enrichment():
    company = {
        "denomination": "RESTO PARIS SAS",
        "commune": "PARIS",
        "dept": "75",
        "code_naf": "56.10A",
        "date_creation": "2026-05-09",
        "siren": "987654321",
    }
    score_result = _base_score_result(
        dirigeant_nom="DUPONT",
        dirigeant_prenom="Jean",
        dirigeant_email="jean@example.com",
        site_web="https://example.com",
        capital_social=10000,
    )
    msg = format_lead_alert(company, score_result)
    assert "Jean DUPONT" in msg
    assert "jean@example.com" in msg
    assert "https://example.com" in msg
    assert "10000" in msg
    print("OK: test_format_lead_alert_with_enrichment")


def test_send_telegram_no_config():
    with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""}):
        result = send_telegram_alert("test")
        assert result is False
    print("OK: test_send_telegram_no_config")


def test_run_pipeline_dry_run():
    fake_companies = [
        {
            "siren": "123456789",
            "siret": "12345678900001",
            "denomination": "RESTO PARIS SAS",
            "forme_juridique": "5710",
            "code_naf": "56.10A",
            "dept": "75",
            "commune": "PARIS",
            "date_creation": "2026-05-09",
        }
    ]
    with (
        patch(
            "apps.leadcommercial.pipeline.fetch_and_parse_idf",
            return_value=fake_companies,
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_enrichment",
            return_value={
                "dirigeant_nom": "",
                "dirigeant_prenom": "",
                "dirigeant_email": "",
                "site_web": "",
                "capital_social": None,
            },
        ),
    ):
        leads = run_pipeline(dry_run=True)
    assert len(leads) == 1
    assert leads[0]["siren"] == "123456789"
    assert leads[0]["score"] >= 50
    print("OK: test_run_pipeline_dry_run")


def test_run_pipeline_enrichment_merged():
    fake_companies = [
        {
            "siren": "111222333",
            "siret": "11122233300001",
            "denomination": "LE BON PLAT SAS",
            "forme_juridique": "5710",
            "code_naf": "56.10A",
            "dept": "92",
            "commune": "BOULOGNE",
            "date_creation": "2026-05-09",
        }
    ]
    fake_enrichment = {
        "dirigeant_nom": "MARTIN",
        "dirigeant_prenom": "Sophie",
        "dirigeant_email": "sophie@lebonplat.fr",
        "site_web": "https://lebonplat.fr",
        "capital_social": 5000,
    }
    with (
        patch(
            "apps.leadcommercial.pipeline.fetch_and_parse_idf",
            return_value=fake_companies,
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_enrichment",
            return_value=fake_enrichment,
        ),
    ):
        leads = run_pipeline(dry_run=True)
    assert len(leads) == 1
    lead = leads[0]
    assert lead["dirigeant_nom"] == "MARTIN"
    assert lead["dirigeant_prenom"] == "Sophie"
    assert lead["dirigeant_email"] == "sophie@lebonplat.fr"
    assert lead["site_web"] == "https://lebonplat.fr"
    assert lead["capital_social"] == 5000
    print("OK: test_run_pipeline_enrichment_merged")


def test_run_pipeline_no_leads():
    with patch("apps.leadcommercial.pipeline.fetch_and_parse_idf", return_value=[]):
        leads = run_pipeline(dry_run=True)
        assert leads == []
    print("OK: test_run_pipeline_no_leads")


def _fake_company() -> dict:
    return {
        "siren": "123456789",
        "siret": "12345678900001",
        "denomination": "RESTO PARIS SAS",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "dept": "75",
        "commune": "PARIS",
        "date_creation": "2026-05-09",
    }


def _empty_enrichment() -> dict:
    return {
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }


def test_run_pipeline_persists_lead():
    with (
        patch(
            "apps.leadcommercial.pipeline.fetch_and_parse_idf",
            return_value=[_fake_company()],
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_enrichment",
            return_value=_empty_enrichment(),
        ),
        patch(
            "apps.leadcommercial.pipeline.persist_lead", return_value=True
        ) as mock_persist,
        patch("apps.leadcommercial.pipeline.send_telegram_alert", return_value=True),
    ):
        leads = run_pipeline(dry_run=False)

    assert len(leads) == 1
    assert leads[0]["siren"] == "123456789"
    mock_persist.assert_called_once()
    print("OK: test_run_pipeline_persists_lead")


def test_run_pipeline_locked_lead_skipped():
    with (
        patch(
            "apps.leadcommercial.pipeline.fetch_and_parse_idf",
            return_value=[_fake_company()],
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_enrichment",
            return_value=_empty_enrichment(),
        ),
        patch(
            "apps.leadcommercial.pipeline.persist_lead", return_value=False
        ),
        patch(
            "apps.leadcommercial.pipeline.send_telegram_alert"
        ) as mock_telegram,
    ):
        leads = run_pipeline(dry_run=False)

    assert leads == []
    mock_telegram.assert_not_called()
    print("OK: test_run_pipeline_locked_lead_skipped")


def test_run_pipeline_with_icp():
    """ICP is fetched from Supabase and forwarded to score_lead when CABINET_ID is set."""
    fake_icp = {
        "secteurs": ["62.01Z"],
        "zone_deps": ["75"],
        "forme_juridique": ["5710"],
        "signaux_prioritaires": ["creation"],
        "signaux_exclus": [],
        "scoring_rules": {},
    }
    company = {**_fake_company(), "code_naf": "62.01Z"}  # ICP sector, not in default NAF
    with (
        patch(
            "apps.leadcommercial.pipeline.fetch_and_parse_idf",
            return_value=[company],
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_enrichment",
            return_value=_empty_enrichment(),
        ),
        patch(
            "apps.leadcommercial.pipeline.fetch_icp", return_value=fake_icp
        ) as mock_fetch_icp,
        patch("apps.leadcommercial.pipeline.persist_lead", return_value=True),
        patch("apps.leadcommercial.pipeline.send_telegram_alert", return_value=True),
        patch.dict(os.environ, {"CABINET_ID": "cabinet-test-uuid"}),
    ):
        leads = run_pipeline(dry_run=False)

    mock_fetch_icp.assert_called_once_with("cabinet-test-uuid")
    assert len(leads) == 1
    # Company in ICP sector 62.01Z must be qualified (score > 50)
    assert leads[0]["score"] >= 50
    print("OK: test_run_pipeline_with_icp")


if __name__ == "__main__":
    test_format_lead_alert()
    test_format_lead_alert_with_enrichment()
    test_send_telegram_no_config()
    test_run_pipeline_dry_run()
    test_run_pipeline_enrichment_merged()
    test_run_pipeline_no_leads()
    test_run_pipeline_persists_lead()
    test_run_pipeline_locked_lead_skipped()
    test_run_pipeline_with_icp()
    print()
    print("9/9 tests passes !")
