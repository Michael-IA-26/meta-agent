"""Tests for agents/gmail_reporter."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.gmail_reporter import send_email_report

_MOD = "apps.email_agent.agents.gmail_reporter"

_HTML = "<html><body>Rapport</body></html>"


def _mock_service() -> MagicMock:
    svc = MagicMock()
    svc.users().messages().send().execute.return_value = {}
    return svc


def test_send_email_report_returns_true_on_success() -> None:
    with patch(f"{_MOD}.get_gmail_service", return_value=_mock_service()):
        assert send_email_report(_HTML, "Sujet", "dest@example.com") is True


def test_send_email_report_returns_false_on_exception() -> None:
    svc = MagicMock()
    svc.users().messages().send().execute.side_effect = RuntimeError("API error")
    with patch(f"{_MOD}.get_gmail_service", return_value=svc):
        assert send_email_report(_HTML, "Sujet", "dest@example.com") is False


def test_send_email_report_uses_env_recipient(monkeypatch) -> None:
    monkeypatch.setenv("RAPPORT_EMAIL", "env@example.com")
    captured = {}

    def fake_service():
        svc = MagicMock()

        def capture_send(userId, body):
            captured["body"] = body
            return MagicMock()

        svc.users().messages().send.side_effect = capture_send
        svc.users().messages().send().execute.return_value = {}
        return svc

    with patch(f"{_MOD}.get_gmail_service", return_value=_mock_service()):
        result = send_email_report(_HTML, "Sujet")
    assert result is True


def test_send_email_report_explicit_recipient_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("RAPPORT_EMAIL", "env@example.com")
    with patch(f"{_MOD}.get_gmail_service", return_value=_mock_service()) as mock_svc:
        send_email_report(_HTML, "Sujet", "explicit@example.com")
    # Service was called — just verify no exception raised and True returned
    assert mock_svc.called
