"""Tests outlook_fetcher + outlook_client (Microsoft Graph mocké)."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.outlook_fetcher import fetch_emails

_FETCHER_MOD = "apps.email_agent.agents.outlook_fetcher"
_CLIENT_MOD = "apps.email_agent.outlook_client"

_GRAPH_RESPONSE = {
    "value": [
        {
            "id": "msg-001",
            "subject": "Facture Metro mai 2026",
            "from": {"emailAddress": {"address": "compta@metro.fr"}},
            "receivedDateTime": "2026-05-28T08:00:00Z",
            "body": {"content": "<p>Veuillez trouver ci-joint la facture.</p>", "contentType": "html"},
        },
        {
            "id": "msg-002",
            "subject": "Relance paiement",
            "from": {"emailAddress": {"address": "client@cihan.fr"}},
            "receivedDateTime": "2026-05-29T09:30:00Z",
            "body": {"content": "Rappel : facture en attente.", "contentType": "text"},
        },
    ]
}


class TestFetchEmails:
    def test_returns_list(self) -> None:
        with patch(f"{_FETCHER_MOD}.get_emails", return_value=[]) as mock:
            result = fetch_emails()
        mock.assert_called_once_with(max_results=20)
        assert result == []

    def test_custom_max_results(self) -> None:
        with patch(f"{_FETCHER_MOD}.get_emails", return_value=[]) as mock:
            fetch_emails(max_results=5)
        mock.assert_called_once_with(max_results=5)

    def test_propagates_exception(self) -> None:
        with patch(f"{_FETCHER_MOD}.get_emails", side_effect=RuntimeError("auth failed")):
            with pytest.raises(RuntimeError, match="auth failed"):
                fetch_emails()


class TestGetEmails:
    def test_maps_graph_response_correctly(self) -> None:
        with patch(f"{_CLIENT_MOD}.graph_get", return_value=_GRAPH_RESPONSE):
            from apps.email_agent.outlook_client import get_emails
            result = get_emails()
        assert len(result) == 2
        assert result[0]["id"] == "msg-001"
        assert result[0]["from"] == "compta@metro.fr"
        assert result[0]["subject"] == "Facture Metro mai 2026"
        assert len(result[0]["body"]) <= 500

    def test_strips_html_from_body(self) -> None:
        with patch(f"{_CLIENT_MOD}.graph_get", return_value=_GRAPH_RESPONSE):
            from apps.email_agent.outlook_client import get_emails
            result = get_emails()
        assert "<p>" not in result[0]["body"]

    def test_empty_inbox(self) -> None:
        with patch(f"{_CLIENT_MOD}.graph_get", return_value={"value": []}):
            from apps.email_agent.outlook_client import get_emails
            assert get_emails() == []

    def test_missing_subject_defaults_to_sans_objet(self) -> None:
        response = {"value": [{
            "id": "msg-003",
            "subject": None,
            "from": {"emailAddress": {"address": "x@y.com"}},
            "receivedDateTime": "2026-05-30T10:00:00Z",
            "body": {"content": "body", "contentType": "text"},
        }]}
        with patch(f"{_CLIENT_MOD}.graph_get", return_value=response):
            from apps.email_agent.outlook_client import get_emails
            result = get_emails()
        assert result[0]["subject"] == "Sans objet"


class TestGetAccessToken:
    @patch("msal.ConfidentialClientApplication")
    def test_raises_on_auth_failure(self, mock_msal: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_app = MagicMock()
        mock_app.acquire_token_by_refresh_token.return_value = {
            "error": "invalid_grant",
            "error_description": "Refresh token expired",
        }
        mock_msal.return_value = mock_app
        monkeypatch.setenv("OUTLOOK_CLIENT_ID", "cid")
        monkeypatch.setenv("OUTLOOK_CLIENT_SECRET", "csec")
        monkeypatch.setenv("OUTLOOK_TENANT_ID", "tid")
        monkeypatch.setenv("OUTLOOK_REFRESH_TOKEN", "expired-token")
        from apps.email_agent.outlook_client import _get_access_token
        with pytest.raises(RuntimeError, match="Outlook auth failed"):
            _get_access_token()

    def test_raises_on_missing_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k in ["OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_TENANT_ID", "OUTLOOK_REFRESH_TOKEN"]:
            monkeypatch.delenv(k, raising=False)
        from apps.email_agent.outlook_client import _get_access_token
        with pytest.raises(KeyError):
            _get_access_token()


_REPORTER_MOD = "apps.email_agent.agents.outlook_reporter"


class TestSendEmailReport:
    @patch(f"{_REPORTER_MOD}.graph_post")
    def test_sends_to_default_recipient(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAPPORT_EMAIL", raising=False)
        from apps.email_agent.agents.outlook_reporter import send_email_report
        result = send_email_report("<p>ok</p>", "Rapport du jour")
        assert result is True
        mock_post.assert_called_once()
        payload = mock_post.call_args[0][1]
        assert payload["message"]["toRecipients"][0]["emailAddress"]["address"] == "michael@myvesper.fr"

    @patch(f"{_REPORTER_MOD}.graph_post")
    def test_sends_to_env_recipient(self, mock_post: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAPPORT_EMAIL", "other@jmpartners.fr")
        from apps.email_agent.agents.outlook_reporter import send_email_report
        send_email_report("<p>ok</p>", "Rapport")
        payload = mock_post.call_args[0][1]
        assert payload["message"]["toRecipients"][0]["emailAddress"]["address"] == "other@jmpartners.fr"

    @patch(f"{_REPORTER_MOD}.graph_post", side_effect=Exception("network error"))
    def test_returns_false_on_error(self, mock_post: MagicMock) -> None:
        from apps.email_agent.agents.outlook_reporter import send_email_report
        assert send_email_report("<p>ok</p>", "Rapport") is False
