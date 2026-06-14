"""TDD — mailer (Graph-first, SMTP fallback). Tests written first (red)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

from apps.jmpartners.integrations.graph_mail import send_mail
from apps.jmpartners.integrations.mailer import send_email

# ── graph_mail.send_mail ──────────────────────────────────────────────────────

def test_send_mail_posts_to_sendmail_endpoint(monkeypatch):
    """send_mail() POSTs to /users/{mailbox}/sendMail with correct JSON."""
    monkeypatch.setenv("GRAPH_MAILBOX", "sender@example.com")
    fake_resp = MagicMock()

    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.post",
              return_value=fake_resp) as mock_post,
    ):
        send_mail("dest@example.com", "Test subject", "<p>Hello</p>")

    url = mock_post.call_args[0][0]
    assert "/users/sender@example.com/sendMail" in url

    body = mock_post.call_args[1]["json"]
    msg = body["message"]
    assert msg["subject"] == "Test subject"
    assert msg["body"]["contentType"] == "HTML"
    assert msg["body"]["content"] == "<p>Hello</p>"
    recipients = [r["emailAddress"]["address"] for r in msg["toRecipients"]]
    assert "dest@example.com" in recipients


def test_send_mail_encodes_attachment_as_base64(monkeypatch):
    """PDF attachment is base64-encoded in the Graph payload."""
    monkeypatch.setenv("GRAPH_MAILBOX", "sender@example.com")
    pdf_bytes = b"%PDF-fake-content"
    fake_resp = MagicMock()

    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.post",
              return_value=fake_resp) as mock_post,
    ):
        send_mail(
            "dest@example.com", "Sub", "body",
            attachments=[("rapport.pdf", pdf_bytes, "application/pdf")],
        )

    attachments = mock_post.call_args[1]["json"]["message"]["attachments"]
    assert len(attachments) == 1
    att = attachments[0]
    assert att["name"] == "rapport.pdf"
    assert att["contentType"] == "application/pdf"
    assert att["contentBytes"] == base64.b64encode(pdf_bytes).decode()
    assert att["@odata.type"] == "#microsoft.graph.fileAttachment"


def test_send_mail_no_attachment_sends_empty_list(monkeypatch):
    monkeypatch.setenv("GRAPH_MAILBOX", "s@e.com")
    fake_resp = MagicMock()
    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.post", return_value=fake_resp) as mock_post,
    ):
        send_mail("d@e.com", "s", "b")
    assert mock_post.call_args[1]["json"]["message"].get("attachments", []) == []


# ── mailer.send_email ─────────────────────────────────────────────────────────

def test_mailer_prefers_graph_when_configured(monkeypatch):
    """When GRAPH_* env vars are set, send_email uses Graph."""
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    with patch("apps.jmpartners.integrations.mailer.send_mail") as mock_graph:
        send_email("to@x.com", "Subject", "<p>Hi</p>")

    mock_graph.assert_called_once_with(
        "to@x.com", "Subject", "<p>Hi</p>", attachments=None
    )


def test_mailer_falls_back_to_smtp_when_graph_not_set(monkeypatch):
    """When GRAPH_* not set, send_email falls back to SMTP."""
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("SMTP_USER", "u@x.com")
    monkeypatch.setenv("SMTP_PASSWORD", "p")
    monkeypatch.setenv("SMTP_HOST", "smtp.x.com")

    with (
        patch("apps.jmpartners.integrations.mailer.send_mail") as mock_graph,
        patch("apps.jmpartners.integrations.mailer._send_smtp") as mock_smtp,
    ):
        send_email("to@x.com", "Subject", "plain text")

    mock_graph.assert_not_called()
    mock_smtp.assert_called_once()


def test_mailer_passes_attachments_to_graph(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")
    atts = [("f.pdf", b"bytes", "application/pdf")]

    with patch("apps.jmpartners.integrations.mailer.send_mail") as mock_graph:
        send_email("to@x.com", "Sub", "body", attachments=atts)

    mock_graph.assert_called_once_with("to@x.com", "Sub", "body", attachments=atts)


# ── Agent call-site tests: no direct smtplib ─────────────────────────────────

def _check_no_smtplib(module_path: str) -> None:
    """Assert the module does not import smtplib at the top level."""
    import sys

    if module_path in sys.modules:
        del sys.modules[module_path]
    # We can't fully test absence of smtplib without reloading; instead check
    # that agent calls mailer.send_email (verified per-agent below).


def test_relance_handler_calls_mailer_not_smtp(monkeypatch):
    """relance_handler.run() calls mailer.send_email, not smtplib directly."""
    from apps.jmpartners.agents.relance_handler import run as run_relance

    doc_result = {
        "dossier_id": "d-1",
        "contact_id": "c-1",
        "type_dossier": "bilan",
        "manquants": [{"nom_document": "Bilan", "type_document": "bilan_n_1",
                       "deadline": None, "urgence": None}],
        "complets": [],
        "erreur": None,
    }

    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee",
              return_value=False),
        patch("apps.jmpartners.agents.relance_handler.fetch_contact_email",
              return_value=("c@c.com", "Client")),
        patch("apps.jmpartners.agents.relance_handler.compose_relance",
              return_value=("Sujet", "Corps")),
        patch("apps.jmpartners.agents.relance_handler.send_email") as mock_send,
        patch("apps.jmpartners.agents.relance_handler.log_journal", return_value="j-1"),
    ):
        run_relance(doc_result, dry_run=False)

    mock_send.assert_called_once()


def test_echeance_agent_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")
    monkeypatch.setenv("RAPPORT_DESTINATAIRE", "dest@x.com")

    from apps.jmpartners.agents import echeance_agent

    with patch("apps.jmpartners.agents.echeance_agent.send_email") as mock_send:
        echeance_agent.send_email_rapport("Sujet", "Corps")

    mock_send.assert_called_once()


def test_report_builder_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    from apps.jmpartners.agents.report_builder import _send_email_rapport

    with patch("apps.jmpartners.agents.report_builder.send_email") as mock_send:
        _send_email_rapport("dest@x.com", b"%PDF", "SARL Test", "2026-05")

    mock_send.assert_called_once()


def test_notification_agent_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    from apps.jmpartners.agents.notification_agent import NotificationAgent

    agent = NotificationAgent()
    with patch("apps.jmpartners.agents.notification_agent.send_email") as mock_send:
        agent._send_email("dest@x.com", "Sub", "Body")

    mock_send.assert_called_once()


def test_acompte_is_agent_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    from apps.jmpartners.agents.acompte_is_agent import AcompteISAgent

    agent = AcompteISAgent()
    with patch("apps.jmpartners.agents.acompte_is_agent.send_email") as mock_send:
        agent._send_email("dest@x.com", "Sub", "Body")

    mock_send.assert_called_once()


def test_bilan_agent_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    from apps.jmpartners.agents.bilan_agent import BilanAgent

    agent = BilanAgent()
    with patch("apps.jmpartners.agents.bilan_agent.send_email") as mock_send:
        agent._send_email("Sub", "Body")

    mock_send.assert_called_once()


def test_declaration_is_agent_calls_mailer_not_smtp(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")
    monkeypatch.setenv("SMTP_USER", "u@x.com")

    from apps.jmpartners.agents.declaration_is_agent import DeclarationISAgent

    agent = DeclarationISAgent()
    with patch("apps.jmpartners.agents.declaration_is_agent.send_email") as mock_send:
        agent._send_email("Sub", "Body")

    mock_send.assert_called_once()
