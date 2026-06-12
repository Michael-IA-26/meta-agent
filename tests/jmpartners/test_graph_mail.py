"""Tests — graph_mail integration (zero network)."""

from __future__ import annotations

import base64
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.mail_handler import run
from apps.jmpartners.integrations import graph_mail

# ── get_token ────────────────────────────────────────────────────────────────

def test_get_token_returns_access_token(monkeypatch):
    """get_token() builds a ConfidentialClientApplication and returns the token."""
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant-x")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client-x")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "secret-x")

    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {"access_token": "tok-abc"}

    with patch("apps.jmpartners.integrations.graph_mail.msal.ConfidentialClientApplication",
               return_value=mock_app) as mock_cls:
        token = graph_mail.get_token()

    mock_cls.assert_called_once_with(
        "client-x",
        authority="https://login.microsoftonline.com/tenant-x",
        client_credential="secret-x",
    )
    mock_app.acquire_token_for_client.assert_called_once_with(
        scopes=["https://graph.microsoft.com/.default"]
    )
    assert token == "tok-abc"


def test_get_token_raises_on_error(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")

    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Bad credentials",
    }
    with patch("apps.jmpartners.integrations.graph_mail.msal.ConfidentialClientApplication",
               return_value=mock_app):
        with pytest.raises(RuntimeError, match="MSAL token error"):
            graph_mail.get_token()


# ── fetch_unread ─────────────────────────────────────────────────────────────

def test_fetch_unread_calls_correct_url(monkeypatch):
    """fetch_unread() hits GET /users/{mailbox}/mailFolders/Inbox/messages with expected params."""
    monkeypatch.setenv("GRAPH_MAILBOX", "inbox@example.com")

    fake_response = MagicMock()
    fake_response.json.return_value = {"value": [{"id": "msg-1"}]}

    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.get", return_value=fake_response) as mock_get,
    ):
        result = graph_mail.fetch_unread()

    call_url = mock_get.call_args[0][0]
    assert "/users/inbox@example.com/mailFolders/Inbox/messages" in call_url
    assert "$filter=isRead eq false" in call_url
    assert "$expand=attachments" in call_url
    assert "$top=25" in call_url
    assert result == [{"id": "msg-1"}]


def test_fetch_unread_explicit_mailbox(monkeypatch):
    fake_response = MagicMock()
    fake_response.json.return_value = {"value": []}

    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.get", return_value=fake_response) as mock_get,
    ):
        graph_mail.fetch_unread(mailbox="other@example.com")

    assert "/users/other@example.com/" in mock_get.call_args[0][0]


def test_fetch_unread_raises_without_mailbox(monkeypatch):
    monkeypatch.delenv("GRAPH_MAILBOX", raising=False)
    with pytest.raises(ValueError, match="GRAPH_MAILBOX"):
        graph_mail.fetch_unread(mailbox="")


# ── decode_attachments ───────────────────────────────────────────────────────

def test_decode_attachments_decodes_base64():
    """decode_attachments returns (filename, raw_bytes) for fileAttachments."""
    raw = b"PDF content"
    encoded = base64.b64encode(raw).decode()
    message = {
        "attachments": [
            {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": "facture.pdf",
                "contentBytes": encoded,
            }
        ]
    }
    result = graph_mail.decode_attachments(message)
    assert len(result) == 1
    assert result[0] == ("facture.pdf", raw)


def test_decode_attachments_ignores_non_file_attachments():
    message = {
        "attachments": [
            {"@odata.type": "#microsoft.graph.referenceAttachment", "name": "link"}
        ]
    }
    assert graph_mail.decode_attachments(message) == []


def test_decode_attachments_empty():
    assert graph_mail.decode_attachments({}) == []
    assert graph_mail.decode_attachments({"attachments": []}) == []


# ── mark_read ────────────────────────────────────────────────────────────────

def test_mark_read_issues_patch(monkeypatch):
    monkeypatch.setenv("GRAPH_MAILBOX", "box@example.com")
    fake_response = MagicMock()

    with (
        patch("apps.jmpartners.integrations.graph_mail.get_token", return_value="tok"),
        patch("apps.jmpartners.integrations.graph_mail.httpx.patch", return_value=fake_response) as mock_patch,
    ):
        graph_mail.mark_read("msg-42")

    call_url = mock_patch.call_args[0][0]
    assert "/users/box@example.com/messages/msg-42" in call_url
    assert mock_patch.call_args[1]["json"] == {"isRead": True}


# ── mail_handler (Graph) ─────────────────────────────────────────────────────


def _base_env(monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "t")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "c")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "s")
    monkeypatch.setenv("GRAPH_MAILBOX", "box@example.com")


def _graph_message(msg_id="m1", from_addr="c@c.com", subject="Sub", body="Body", attachments=None):
    return {
        "id": msg_id,
        "from": {"emailAddress": {"address": from_addr}},
        "subject": subject,
        "body": {"content": body},
        "attachments": attachments or [],
    }


def test_graph_non_configure_retourne_immediatement(monkeypatch):
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)

    result = run(dry_run=True)

    assert result["traites"] == 0
    assert "Graph non configuré" in result["erreurs"]


def test_nouvelle_piece_jointe_upload_et_insert(monkeypatch):
    """Nouvelle pièce jointe (hash absent) → upload Storage + insert documents."""
    _base_env(monkeypatch)
    raw = b"PDF content"
    encoded = base64.b64encode(raw).decode()
    msg = _graph_message(
        attachments=[{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "facture.pdf",
            "contentBytes": encoded,
        }]
    )

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{"id": "doc-1"}]
    mock_supabase.storage.from_.return_value.upload.return_value = {}

    with (
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client", return_value=mock_supabase),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread", return_value=[msg]),
        patch("apps.jmpartners.agents.mail_handler.identify_contact", return_value=("c-1", "Client")),
        patch("apps.jmpartners.agents.mail_handler.classify_request", return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value="j-1"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
    ):
        result = run(dry_run=False)

    assert result["traites"] == 1
    mock_supabase.storage.from_.assert_called_with("documents")
    mock_supabase.storage.from_.return_value.upload.assert_called_once()
    mock_supabase.table.return_value.insert.assert_called()


def test_piece_jointe_dupliquee_skip(monkeypatch):
    """Hash déjà présent → ni upload, ni insert."""
    _base_env(monkeypatch)
    raw = b"already there"
    encoded = base64.b64encode(raw).decode()
    msg = _graph_message(
        attachments=[{
            "@odata.type": "#microsoft.graph.fileAttachment",
            "name": "dup.pdf",
            "contentBytes": encoded,
        }]
    )

    mock_supabase = MagicMock()
    # hash found → document exists
    mock_supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "existing"}]

    with (
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client", return_value=mock_supabase),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread", return_value=[msg]),
        patch("apps.jmpartners.agents.mail_handler.identify_contact", return_value=(None, None)),
        patch("apps.jmpartners.agents.mail_handler.classify_request", return_value="autre"),
        patch("apps.jmpartners.agents.mail_handler.log_journal", return_value=None),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
    ):
        result = run(dry_run=False)

    assert result["traites"] == 1
    mock_supabase.storage.from_.assert_not_called()
    assert result["emails"][0]["pieces_jointes"] == 0


def test_identify_contact_classify_log_appeles(monkeypatch):
    """identify_contact, classify_request et log_journal sont tous appelés."""
    _base_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread",
              return_value=[_graph_message()]),
        patch("apps.jmpartners.agents.mail_handler.identify_contact",
              return_value=("c-1", "Client")) as mock_id,
        patch("apps.jmpartners.agents.mail_handler.classify_request",
              return_value="relance") as mock_cls,
        patch("apps.jmpartners.agents.mail_handler.log_journal",
              return_value="j-1") as mock_log,
        patch("apps.jmpartners.agents.mail_handler.graph_mail.mark_read"),
        patch("apps.jmpartners.agents.mail_handler._document_exists", return_value=False),
        patch("apps.jmpartners.agents.mail_handler._upload_and_insert"),
    ):
        run(dry_run=False)

    mock_id.assert_called_once()
    mock_cls.assert_called_once()
    mock_log.assert_called_once()


def test_boite_vide_retourne_zero_traites(monkeypatch):
    _base_env(monkeypatch)

    with (
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
        patch("apps.jmpartners.agents.mail_handler.graph_mail.fetch_unread", return_value=[]),
    ):
        result = run(dry_run=True)

    assert result["traites"] == 0
    assert result["erreurs"] == []
