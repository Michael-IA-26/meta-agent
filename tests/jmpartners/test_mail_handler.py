"""Tests TDD — mail_handler (Graph edition)."""

from __future__ import annotations

from unittest.mock import patch

from apps.jmpartners.agents.mail_handler import run


def _graph_env(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")
    monkeypatch.setenv("GRAPH_MAILBOX", "box@example.com")


def _msg(msg_id="m1", from_addr="c@c.com", subject="Sub", body="Body"):
    return {
        "id": msg_id,
        "from": {"emailAddress": {"address": from_addr}},
        "subject": subject,
        "body": {"content": body},
        "attachments": [],
    }


def test_graph_non_configure_retourne_immediatement(monkeypatch):
    """Sans variables Graph, run() retourne sans appel réseau."""
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)

    result = run(dry_run=True)

    assert result["traites"] == 0
    assert "Graph non configuré" in result["erreurs"]


def test_graph_configure_appelle_fetch(monkeypatch):
    """Avec variables Graph, fetch_unread est appelé."""
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[]) as mock_fetch,
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
    ):
        result = run(dry_run=True)

    mock_fetch.assert_called_once()
    assert result["traites"] == 0


def test_happy_path_email_identifie_et_classifie(monkeypatch):
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_msg()]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("contact-1", "SARL Dupont")),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="document_manquant"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value="j-1"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
    ):
        result = run(dry_run=False)

    assert result["traites"] == 1
    assert result["emails"][0]["type_demande"] == "document_manquant"
    assert result["emails"][0]["contact_id"] == "contact-1"


def test_email_contact_inconnu_incremente_non_matches(monkeypatch):
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_msg(from_addr="inconnu@nowhere.com")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact", return_value=(None, None)),
        patch("apps.jmpartners.agents.mail_handler.classify_request", return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
    ):
        result = run(dry_run=False)

    assert result["non_matches"] == 1
    assert result["emails"][0]["contact_id"] is None


def test_dry_run_ninsere_pas_dans_journaux(monkeypatch):
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_msg()]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("c-1", "Contact")),
        patch("apps.jmpartners.agents.mail_handler.classify_request", return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal") as mock_log,
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
    ):
        run(dry_run=True)

    mock_log.assert_not_called()


def test_claude_timeout_fallback_type_autre(monkeypatch):
    """Si classify_request lève une exception, l'email est en erreur."""
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_msg()]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("c-1", "Contact")),
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              side_effect=Exception("Anthropic timeout")),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
    ):
        result = run(dry_run=False)

    assert len(result["erreurs"]) >= 1


def test_corps_email_vide_traite_sans_erreur(monkeypatch):
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_msg(body="")]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.identify_contact", return_value=(None, None)),
        patch("apps.jmpartners.agents.mail_handler.classify_request", return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
    ):
        result = run(dry_run=False)

    assert result["traites"] == 1


def test_boite_vide_retourne_zero_traites(monkeypatch):
    _graph_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread", return_value=[]),
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
    ):
        result = run(dry_run=True)

    assert result["traites"] == 0
    assert result["erreurs"] == []
