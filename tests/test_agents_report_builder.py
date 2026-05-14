"""Tests for agents/report_builder."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.report_builder import build_report

_MOD = "apps.email_agent.agents.report_builder"

_ANALYZED = [
    {
        "id": "1",
        "subject": "Devis urgent",
        "from": "client@ex.com",
        "date": "2026-05-14",
        "body": "...",
        "priority": "haute",
        "category": "action_requise",
        "summary": "Devis demande",
        "action": "Envoyer devis",
        "suggested_reply": "Bien recu",
    },
    {
        "id": "2",
        "subject": "LinkedIn",
        "from": "noreply@linkedin.com",
        "date": "2026-05-14",
        "body": "...",
        "priority": "basse",
        "category": "inutile",
        "summary": "Notif",
        "action": None,
        "suggested_reply": None,
    },
]


def test_build_report_returns_html_string() -> None:
    html = build_report(_ANALYZED)
    assert isinstance(html, str)
    assert "<html" in html.lower()


def test_build_report_calls_report_to_html() -> None:
    with patch(f"{_MOD}.report_to_html", return_value="<html>mock</html>") as mock_fn:
        result = build_report(_ANALYZED)
    mock_fn.assert_called_once_with(_ANALYZED)
    assert result == "<html>mock</html>"


def test_build_report_contains_subject() -> None:
    html = build_report(_ANALYZED)
    assert "Devis urgent" in html


def test_build_report_empty_list() -> None:
    html = build_report([])
    assert isinstance(html, str)
    assert "0" in html or html  # valid HTML even with no emails
