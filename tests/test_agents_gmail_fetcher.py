"""Tests for agents/gmail_fetcher."""
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.gmail_fetcher import fetch_emails

_MOD = "apps.email_agent.agents.gmail_fetcher"

_FAKE_EMAILS = [
    {"id": "1", "subject": "Test", "from": "a@b.com", "date": "2026-01-01", "body": "hi"},
]


def test_fetch_emails_returns_list() -> None:
    with patch(f"{_MOD}.get_emails", return_value=_FAKE_EMAILS) as mock_get:
        result = fetch_emails(max_results=5)
    mock_get.assert_called_once_with(max_results=5)
    assert result == _FAKE_EMAILS


def test_fetch_emails_default_max_results() -> None:
    with patch(f"{_MOD}.get_emails", return_value=[]) as mock_get:
        fetch_emails()
    mock_get.assert_called_once_with(max_results=20)


def test_fetch_emails_empty_inbox() -> None:
    with patch(f"{_MOD}.get_emails", return_value=[]):
        result = fetch_emails()
    assert result == []


def test_fetch_emails_propagates_exception() -> None:
    with patch(f"{_MOD}.get_emails", side_effect=RuntimeError("API down")):
        with pytest.raises(RuntimeError, match="API down"):
            fetch_emails()
