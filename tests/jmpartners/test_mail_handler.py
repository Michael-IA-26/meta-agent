"""Tests resolve_dossier_for_contact — apps/jmpartners/agents/mail_handler.py."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.jmpartners.agents.mail_handler import resolve_dossier_for_contact


def _make_supabase(rows: list[dict] | None = None) -> MagicMock:
    """Build a minimal Supabase mock with fluent select chain."""
    mock = MagicMock()
    result = MagicMock()
    result.data = rows if rows is not None else []
    (
        mock.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value
    ) = result
    return mock


def test_returns_none_when_contact_id_is_none() -> None:
    supabase = _make_supabase()
    assert resolve_dossier_for_contact(supabase, None) is None
    supabase.table.assert_not_called()


def test_returns_dossier_id_when_exactly_one_match() -> None:
    supabase = _make_supabase([{"id": "dossier-abc"}])
    result = resolve_dossier_for_contact(supabase, "contact-123")
    assert result == "dossier-abc"


def test_returns_none_when_no_match() -> None:
    supabase = _make_supabase([])
    assert resolve_dossier_for_contact(supabase, "contact-456") is None


def test_returns_none_when_ambiguous(caplog: pytest.LogCaptureFixture) -> None:
    """Two active dossiers → ambiguous, return None and log warning."""
    supabase = _make_supabase([{"id": "dossier-1"}, {"id": "dossier-2"}])
    import logging
    with caplog.at_level(logging.WARNING, logger="apps.jmpartners.agents.mail_handler"):
        result = resolve_dossier_for_contact(supabase, "contact-789")
    assert result is None
    assert "ambigu" in caplog.text


def test_returns_none_on_supabase_error(caplog: pytest.LogCaptureFixture) -> None:
    supabase = MagicMock()
    supabase.table.side_effect = RuntimeError("Supabase down")
    import logging
    with caplog.at_level(logging.WARNING, logger="apps.jmpartners.agents.mail_handler"):
        result = resolve_dossier_for_contact(supabase, "contact-xyz")
    assert result is None
    assert "Supabase erreur" in caplog.text
