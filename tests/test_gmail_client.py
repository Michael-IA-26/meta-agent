"""Tests for gmail_client — production (env/base64) and local (file) auth modes."""

import base64
import json
import os
import pathlib
import sys
from unittest.mock import ANY, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.gmail_client import (  # noqa: E402
    TOKEN_FILE,
    TOKEN_VESPER_FILE,
    _get_credentials,
    _is_production,
    _load_credentials_from_env,
    _load_credentials_from_file,
    get_gmail_service,
    get_gmail_service_vesper,
)

_MOD = "apps.email_agent.gmail_client"

_FAKE_TOKEN: dict = {
    "token": "tok",
    "refresh_token": "ref",
    "token_uri": "https://oauth2.googleapis.com/token",
    "client_id": "cid",
    "client_secret": "csec",
    "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
}
_FAKE_TOKEN_B64 = base64.b64encode(json.dumps(_FAKE_TOKEN).encode()).decode()


# ---------------------------------------------------------------------------
# _is_production
# ---------------------------------------------------------------------------


def test_is_production_true(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_B64", _FAKE_TOKEN_B64)
    assert _is_production() is True


def test_is_production_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_TOKEN_B64", raising=False)
    assert _is_production() is False


# ---------------------------------------------------------------------------
# _load_credentials_from_env
# ---------------------------------------------------------------------------


def test_load_credentials_from_env_decodes_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_B64", _FAKE_TOKEN_B64)
    mock_creds = MagicMock()
    with patch(f"{_MOD}.Credentials.from_authorized_user_info", return_value=mock_creds) as fn:
        result = _load_credentials_from_env("GMAIL_TOKEN_B64")
    fn.assert_called_once_with(_FAKE_TOKEN, ANY)
    assert result is mock_creds


def test_load_credentials_from_env_missing_var() -> None:
    with pytest.raises(KeyError):
        _load_credentials_from_env("GMAIL_TOKEN_B64_NONEXISTENT")


# ---------------------------------------------------------------------------
# _load_credentials_from_file
# ---------------------------------------------------------------------------


def test_load_credentials_from_file_exists() -> None:
    mock_creds = MagicMock()
    with patch("os.path.exists", return_value=True), patch(
        f"{_MOD}.Credentials.from_authorized_user_file", return_value=mock_creds
    ) as fn:
        result = _load_credentials_from_file("/fake/token.json")
    fn.assert_called_once_with("/fake/token.json", ANY)
    assert result is mock_creds


def test_load_credentials_from_file_missing() -> None:
    with patch("os.path.exists", return_value=False):
        result = _load_credentials_from_file("/fake/token.json")
    assert result is None


# ---------------------------------------------------------------------------
# _get_credentials — production mode
# ---------------------------------------------------------------------------


def test_get_credentials_production_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_B64", _FAKE_TOKEN_B64)
    mock_creds = MagicMock(expired=False)
    with patch(f"{_MOD}._load_credentials_from_env", return_value=mock_creds):
        result = _get_credentials(TOKEN_FILE, "GMAIL_TOKEN_B64")
    mock_creds.refresh.assert_not_called()
    assert result is mock_creds


def test_get_credentials_production_expired_refreshes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GMAIL_TOKEN_B64", _FAKE_TOKEN_B64)
    mock_creds = MagicMock(expired=True, refresh_token="r")
    with patch(f"{_MOD}._load_credentials_from_env", return_value=mock_creds), patch(
        f"{_MOD}.Request"
    ):
        result = _get_credentials(TOKEN_FILE, "GMAIL_TOKEN_B64")
    mock_creds.refresh.assert_called_once()
    assert result is mock_creds


# ---------------------------------------------------------------------------
# _get_credentials — local mode
# ---------------------------------------------------------------------------


def test_get_credentials_local_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GMAIL_TOKEN_B64", raising=False)
    mock_creds = MagicMock(valid=True)
    with patch(f"{_MOD}._load_credentials_from_file", return_value=mock_creds):
        result = _get_credentials(TOKEN_FILE, "GMAIL_TOKEN_B64")
    mock_creds.refresh.assert_not_called()
    assert result is mock_creds


def test_get_credentials_local_expired_refreshes_and_saves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.delenv("GMAIL_TOKEN_B64", raising=False)
    token_file = str(tmp_path / "token.json")
    mock_creds = MagicMock(valid=False, expired=True, refresh_token="r")
    mock_creds.to_json.return_value = '{"token":"new"}'
    with patch(f"{_MOD}._load_credentials_from_file", return_value=mock_creds), patch(
        f"{_MOD}.Request"
    ):
        result = _get_credentials(token_file, "GMAIL_TOKEN_B64")
    mock_creds.refresh.assert_called_once()
    assert os.path.exists(token_file)
    assert result is mock_creds


def test_get_credentials_local_no_file_runs_oauth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.delenv("GMAIL_TOKEN_B64", raising=False)
    token_file = str(tmp_path / "token.json")
    mock_creds = MagicMock(valid=True)
    mock_creds.to_json.return_value = '{"token":"new"}'
    mock_flow = MagicMock()
    mock_flow.run_local_server.return_value = mock_creds
    with patch(f"{_MOD}._load_credentials_from_file", return_value=None), patch(
        f"{_MOD}.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow
    ):
        result = _get_credentials(token_file, "GMAIL_TOKEN_B64")
    mock_flow.run_local_server.assert_called_once_with(port=0)
    assert os.path.exists(token_file)
    assert result is mock_creds


# ---------------------------------------------------------------------------
# get_gmail_service / get_gmail_service_vesper
# ---------------------------------------------------------------------------


def test_get_gmail_service_uses_primary_token() -> None:
    mock_creds = MagicMock()
    mock_service = MagicMock()
    with patch(f"{_MOD}._get_credentials", return_value=mock_creds) as mock_gc, patch(
        f"{_MOD}.build", return_value=mock_service
    ) as mock_build:
        svc = get_gmail_service()
    args = mock_gc.call_args[0]
    assert args[0] == TOKEN_FILE
    assert args[1] == "GMAIL_TOKEN_B64"
    mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
    assert svc is mock_service


def test_get_gmail_service_vesper_uses_vesper_token() -> None:
    mock_creds = MagicMock()
    mock_service = MagicMock()
    with patch(f"{_MOD}._get_credentials", return_value=mock_creds) as mock_gc, patch(
        f"{_MOD}.build", return_value=mock_service
    ) as mock_build:
        svc = get_gmail_service_vesper()
    args = mock_gc.call_args[0]
    assert args[0] == TOKEN_VESPER_FILE
    assert args[1] == "GMAIL_TOKEN_VESPER_B64"
    mock_build.assert_called_once_with("gmail", "v1", credentials=mock_creds)
    assert svc is mock_service
