"""Tests for apps.email_agent.gmail_client."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.gmail_client import (  # noqa: E402
    TOKEN_FILE,
    get_emails,
    get_gmail_service,
)

_MOD = "apps.email_agent.gmail_client"


def _make_creds(valid: bool = True, expired: bool = False, has_refresh: bool = True) -> MagicMock:
    creds = MagicMock()
    creds.valid = valid
    creds.expired = expired
    creds.refresh_token = "refresh" if has_refresh else None
    creds.to_json.return_value = '{"token": "tok"}'
    return creds


def test_token_file_constant_is_string():
    assert isinstance(TOKEN_FILE, str)
    assert TOKEN_FILE.endswith(".json")


def test_get_gmail_service_uses_existing_valid_creds(tmp_path):
    creds = _make_creds(valid=True)
    with (
        patch(f"{_MOD}.os.path.exists", return_value=True),
        patch(f"{_MOD}.Credentials.from_authorized_user_file", return_value=creds),
        patch(f"{_MOD}.build") as mock_build,
    ):
        mock_build.return_value = MagicMock()
        result = get_gmail_service()
    mock_build.assert_called_once_with("gmail", "v1", credentials=creds)
    assert result is mock_build.return_value


def test_get_gmail_service_refreshes_expired_creds():
    creds = _make_creds(valid=False, expired=True, has_refresh=True)
    with (
        patch(f"{_MOD}.os.path.exists", return_value=True),
        patch(f"{_MOD}.Credentials.from_authorized_user_file", return_value=creds),
        patch(f"{_MOD}.build") as mock_build,
        patch("builtins.open", MagicMock()),
    ):
        mock_build.return_value = MagicMock()
        get_gmail_service()
    creds.refresh.assert_called_once()


def test_get_gmail_service_no_token_file():
    with (
        patch(f"{_MOD}.os.path.exists", return_value=False),
        patch(f"{_MOD}.InstalledAppFlow.from_client_secrets_file") as mock_flow,
        patch(f"{_MOD}.build") as mock_build,
        patch("builtins.open", MagicMock()),
    ):
        mock_creds = _make_creds(valid=True)
        mock_flow.return_value.run_local_server.return_value = mock_creds
        mock_build.return_value = MagicMock()
        get_gmail_service()
    mock_flow.assert_called_once()


def test_get_emails_returns_list():
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg1"}, {"id": "msg2"}]
    }
    mock_service.users().messages().get().execute.return_value = {
        "payload": {
            "headers": [
                {"name": "From", "value": "test@example.com"},
                {"name": "Subject", "value": "Test Subject"},
                {"name": "Date", "value": "2026-05-21"},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": "SGVsbG8="}}
            ],
        }
    }
    with patch(f"{_MOD}.get_gmail_service", return_value=mock_service):
        emails = get_emails(max_results=2)
    assert isinstance(emails, list)


def test_get_emails_empty_inbox():
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {"messages": []}
    with patch(f"{_MOD}.get_gmail_service", return_value=mock_service):
        emails = get_emails(max_results=5)
    assert emails == []


def test_get_emails_no_messages_key():
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {}
    with patch(f"{_MOD}.get_gmail_service", return_value=mock_service):
        emails = get_emails(max_results=5)
    assert emails == []
