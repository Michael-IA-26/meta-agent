"""Tests for agents/supabase_writer."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.supabase_writer import write_email, write_kpis

_MOD = "apps.email_agent.agents.supabase_writer"

_ANALYZED = {
    "id": "1",
    "subject": "Test",
    "from": "a@b.com",
    "date": "2026-05-14",
    "body": "hi",
    "priority": "haute",
    "category": "action_requise",
    "summary": "A faire",
    "action": "Repondre",
    "suggested_reply": None,
}

_KPI_RESULT = {
    "emails_analyses": 1,
    "temps_theorique_min": 45,
    "temps_agent_min": 2.0,
    "temps_gagne_min": 43.0,
    "gain_pourcentage": 95.6,
    "valeur_estimee_eur": 57.3,
    "semaine": "2026-W20",
}


def test_write_email_returns_true_on_success() -> None:
    with patch(f"{_MOD}._save_email", return_value=True):
        assert write_email(_ANALYZED) is True


def test_write_email_returns_false_on_failure() -> None:
    with patch(f"{_MOD}._save_email", return_value=False):
        assert write_email(_ANALYZED) is False


def test_write_email_calls_save_email_with_analyzed() -> None:
    with patch(f"{_MOD}._save_email", return_value=True) as mock_save:
        write_email(_ANALYZED)
    mock_save.assert_called_once_with(_ANALYZED)


def test_write_kpis_returns_kpi_result() -> None:
    with patch(f"{_MOD}.calculate_and_save_kpis", return_value=_KPI_RESULT):
        result = write_kpis([_ANALYZED], temps_agent_sec=120.0)
    assert result["emails_analyses"] == 1
    assert result["semaine"] == "2026-W20"


def test_write_kpis_passes_elapsed_seconds() -> None:
    with patch(f"{_MOD}.calculate_and_save_kpis", return_value=_KPI_RESULT) as mock_kpi:
        write_kpis([_ANALYZED], temps_agent_sec=90.5)
    mock_kpi.assert_called_once_with([_ANALYZED], 90.5)


def test_write_kpis_returns_empty_on_failure() -> None:
    with patch(f"{_MOD}.calculate_and_save_kpis", return_value={}):
        result = write_kpis([_ANALYZED], temps_agent_sec=10.0)
    assert result == {}
