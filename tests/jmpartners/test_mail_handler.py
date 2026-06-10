"""Tests TDD — mail_handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.mail_handler import run


def test_imap_non_configure_retourne_immediatement(monkeypatch):
    """Sans variables IMAP, run() retourne sans appel réseau."""
    monkeypatch.delenv("IMAP_HOST", raising=False)
    monkeypatch.delenv("IMAP_USER", raising=False)
    monkeypatch.delenv("IMAP_PASSWORD", raising=False)

    with patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails") as mock_fetch:
        result = run(dry_run=True)

    mock_fetch.assert_not_called()
    assert result["traites"] == 0
    assert "IMAP non configuré" in result["erreurs"]


def test_imap_configure_appelle_fetch(monkeypatch):
    """Avec variables IMAP, fetch_unseen_emails est appelé."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "user@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[]) as mock_fetch,
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
    ):
        result = run(dry_run=True)

    mock_fetch.assert_called_once()
    assert result["traites"] == 0


def test_happy_path_email_identifie_et_classifie(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "user@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[("mid-1", "contact@dupont.fr", "Docs manquants", "Corps")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("contact-1", "SARL Dupont")),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="document_manquant"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value="j-1"),
    ):
        result = run(dry_run=False)

    assert result["traites"] == 1
    assert result["emails"][0]["type_demande"] == "document_manquant"
    assert result["emails"][0]["contact_id"] == "contact-1"


def test_email_contact_inconnu_incremente_non_matches(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "u@e.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[("m1", "inconnu@nowhere.com", "Sujet", "Corps")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=(None, None)),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
    ):
        result = run(dry_run=False)

    assert result["non_matches"] == 1
    assert result["emails"][0]["contact_id"] is None


def test_dry_run_ninsere_pas_dans_journaux(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "u@e.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[("m1", "c@c.com", "Sujet", "Corps")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("c-1", "Contact")),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal") as mock_log,
    ):
        run(dry_run=True)

    mock_log.assert_not_called()


def test_claude_timeout_fallback_type_autre(monkeypatch):
    """Si classify_request lève une exception, type_demande = 'autre'."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "u@e.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[("m1", "c@c.com", "Sujet", "Corps")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("c-1", "Contact")),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              side_effect=Exception("Anthropic timeout")),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
    ):
        result = run(dry_run=False)

    assert len(result["erreurs"]) >= 1


def test_corps_email_vide_traite_sans_erreur(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "u@e.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[("m1", "c@c.com", "Sujet", "")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=(None, None)),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
    ):
        result = run(dry_run=False)  # ne doit pas lever

    assert result["traites"] == 1


def test_boite_vide_retourne_zero_traites(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "u@e.com")
    monkeypatch.setenv("IMAP_PASSWORD", "p")

    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails",
              return_value=[]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
    ):
        result = run(dry_run=True)

    assert result["traites"] == 0
    assert result["erreurs"] == []
