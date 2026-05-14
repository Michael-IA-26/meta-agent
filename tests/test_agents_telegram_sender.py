"""Tests for agents/telegram_sender."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.telegram_sender import send_telegram

_MOD = "apps.email_agent.agents.telegram_sender"

_ANALYZED = [
    {
        "id": "1",
        "subject": "Urgent",
        "from": "a@b.com",
        "date": "2026-05-14",
        "body": "...",
        "priority": "haute",
        "category": "action_requise",
        "summary": "A faire",
        "action": "Repondre",
        "suggested_reply": None,
    }
]

_KPIS = {
    "emails_analyses": 1,
    "temps_theorique_min": 45,
    "temps_agent_min": 2.0,
    "temps_gagne_min": 43.0,
    "gain_pourcentage": 95.6,
    "valeur_estimee_eur": 57.3,
    "semaine": "2026-W20",
}


def test_send_telegram_returns_true_on_success() -> None:
    with patch(f"{_MOD}._tg.send_telegram_report", return_value=True):
        assert send_telegram(_ANALYZED, _KPIS) is True


def test_send_telegram_returns_false_on_failure() -> None:
    with patch(f"{_MOD}._tg.send_telegram_report", return_value=False):
        assert send_telegram(_ANALYZED, _KPIS) is False


def test_send_telegram_passes_emails_and_kpis() -> None:
    with patch(f"{_MOD}._tg.send_telegram_report", return_value=True) as mock_fn:
        send_telegram(_ANALYZED, _KPIS)
    mock_fn.assert_called_once_with(_ANALYZED, _KPIS)


def test_send_telegram_none_kpis_accepted() -> None:
    with patch(f"{_MOD}._tg.send_telegram_report", return_value=True) as mock_fn:
        send_telegram(_ANALYZED, None)
    mock_fn.assert_called_once_with(_ANALYZED, None)
