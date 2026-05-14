"""Tests for apps.leadcommercial.agents.telegram_notifier."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import httpx

from apps.leadcommercial.agents.telegram_notifier import (
    NotifyInput,
    _format_message,
    notify_lead,
)


def _notify_input(**overrides) -> NotifyInput:
    base = NotifyInput(
        siren="123456789",
        denomination="TEST SAS",
        commune="PARIS",
        dept="75",
        code_naf="70.22Z",
        date_creation="2026-05-01",
        score=80,
        signal_type="creation",
        scoring_details=["Signal creation: +100"],
        dirigeant_nom="DUPONT",
        dirigeant_prenom="Jean",
        dirigeant_email="jean@test.com",
        site_web="https://test.com",
        capital_social=10000,
    )
    base.update(overrides)  # type: ignore[typeddict-item]
    return base


def test_notify_lead_no_token_returns_false():
    with (
        patch("apps.leadcommercial.agents.telegram_notifier._BOT_TOKEN", ""),
        patch("apps.leadcommercial.agents.telegram_notifier._CHAT_ID", ""),
    ):
        result = notify_lead(_notify_input())
    assert result is False


def test_notify_lead_no_chat_id_returns_false():
    with (
        patch("apps.leadcommercial.agents.telegram_notifier._BOT_TOKEN", "mytoken"),
        patch("apps.leadcommercial.agents.telegram_notifier._CHAT_ID", ""),
    ):
        result = notify_lead(_notify_input())
    assert result is False


def test_notify_lead_http_error_returns_false():
    with (
        patch("apps.leadcommercial.agents.telegram_notifier._BOT_TOKEN", "tok"),
        patch("apps.leadcommercial.agents.telegram_notifier._CHAT_ID", "123"),
        patch("apps.leadcommercial.agents.telegram_notifier.httpx.post") as mock_post,
    ):
        mock_post.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "400", request=MagicMock(), response=MagicMock()
        )
        result = notify_lead(_notify_input())
    assert result is False


def test_notify_lead_success_returns_true():
    with (
        patch("apps.leadcommercial.agents.telegram_notifier._BOT_TOKEN", "tok"),
        patch("apps.leadcommercial.agents.telegram_notifier._CHAT_ID", "123"),
        patch("apps.leadcommercial.agents.telegram_notifier.httpx.post") as mock_post,
    ):
        mock_post.return_value.raise_for_status = MagicMock()
        result = notify_lead(_notify_input())
    assert result is True


def test_format_message_includes_key_fields():
    msg = _format_message(_notify_input())
    assert "TEST SAS" in msg
    assert "PARIS" in msg
    assert "123456789" in msg
    assert "80/100" in msg
    assert "Jean DUPONT" in msg
    assert "jean@test.com" in msg
    assert "https://test.com" in msg
    assert "10000" in msg


def test_format_message_no_dirigeant_omits_line():
    msg = _format_message(_notify_input(dirigeant_nom="", dirigeant_prenom=""))
    assert "Dirigeant" not in msg


def test_format_message_no_site_omits_line():
    msg = _format_message(_notify_input(site_web=""))
    assert "Site" not in msg
