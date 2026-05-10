import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch

from apps.leadcommercial.pipeline import (
    format_lead_alert,
    run_pipeline,
    send_telegram_alert,
)


def test_format_lead_alert():
    company = {
        "denomination": "TEST SAS",
        "commune": "PARIS",
        "dept": "75",
        "code_naf": "62.01Z",
        "date_creation": "2026-05-09",
        "siren": "123456789",
    }
    score_result = {
        "score": 100,
        "signal_type": "creation",
        "scoring_details": ["Signal creation: +100"],
    }
    msg = format_lead_alert(company, score_result)
    assert "TEST SAS" in msg
    assert "PARIS" in msg
    assert "100/100" in msg
    assert "123456789" in msg
    print("OK: test_format_lead_alert")


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
    with patch(
        "apps.leadcommercial.pipeline.fetch_and_parse_idf", return_value=fake_companies
    ):
        leads = run_pipeline(dry_run=True)
        assert len(leads) == 1
        assert leads[0]["siren"] == "123456789"
        assert leads[0]["score"] >= 50
    print("OK: test_run_pipeline_dry_run")


def test_run_pipeline_no_leads():
    with patch("apps.leadcommercial.pipeline.fetch_and_parse_idf", return_value=[]):
        leads = run_pipeline(dry_run=True)
        assert leads == []
    print("OK: test_run_pipeline_no_leads")


if __name__ == "__main__":
    test_format_lead_alert()
    test_send_telegram_no_config()
    test_run_pipeline_dry_run()
    test_run_pipeline_no_leads()
    print()
    print("4/4 tests passes !")
