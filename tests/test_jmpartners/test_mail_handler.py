"""Tests pour apps.jmpartners.agents.mail_handler."""

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.mail_handler import (
    classify_request,
    decode_str,
    identify_contact,
    log_journal,
    run,
)

# ─── decode_str ──────────────────────────────────────────────────────────────


def test_decode_str_plain():
    assert decode_str("hello") == "hello"


def test_decode_str_bytes():
    assert decode_str(b"hello") == "hello"


def test_decode_str_encoded_header():
    encoded = "=?utf-8?b?SGVsbG8gV29ybGQ=?="
    result = decode_str(encoded)
    assert "Hello World" in result


# ─── identify_contact ─────────────────────────────────────────────────────────


def test_identify_contact_found():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "abc-123", "nom": "Dupont SARL"}
    ]
    cid, nom = identify_contact(supabase, "contact@dupont.fr")
    assert cid == "abc-123"
    assert nom == "Dupont SARL"


def test_identify_contact_not_found():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    cid, nom = identify_contact(supabase, "inconnu@example.com")
    assert cid is None
    assert nom is None


def test_identify_contact_with_display_name():
    supabase = MagicMock()
    supabase.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "xyz-789", "nom": "Martin"}
    ]
    cid, nom = identify_contact(supabase, "Martin Dupont <martin@dupont.com>")
    assert cid == "xyz-789"


def test_identify_contact_supabase_error():
    supabase = MagicMock()
    supabase.table.side_effect = Exception("connection error")
    cid, nom = identify_contact(supabase, "test@test.com")
    assert cid is None
    assert nom is None


# ─── classify_request ─────────────────────────────────────────────────────────


def test_classify_request_document_manquant():
    client = MagicMock()
    msg_mock = MagicMock()
    msg_mock.content = [MagicMock(text='{"type": "document_manquant"}')]
    client.messages.create.return_value = msg_mock
    result = classify_request(
        client, "Documents manquants bilan", "Bonjour, il manque le grand livre"
    )
    assert result == "document_manquant"


def test_classify_request_question_tva():
    client = MagicMock()
    msg_mock = MagicMock()
    msg_mock.content = [MagicMock(text='{"type": "question_tva"}')]
    client.messages.create.return_value = msg_mock
    result = classify_request(client, "Question TVA", "Ma TVA de mai")
    assert result == "question_tva"


def test_classify_request_fallback_on_error():
    client = MagicMock()
    client.messages.create.side_effect = Exception("API down")
    result = classify_request(client, "Re:", "Bonjour")
    assert result == "autre"


def test_classify_request_invalid_type_returns_autre():
    client = MagicMock()
    msg_mock = MagicMock()
    msg_mock.content = [MagicMock(text='{"type": "categorie_inconnue"}')]
    client.messages.create.return_value = msg_mock
    result = classify_request(client, "test", "test")
    assert result == "autre"


# ─── log_journal ─────────────────────────────────────────────────────────────


def test_log_journal_success():
    supabase = MagicMock()
    supabase.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "journal-001"}
    ]
    jid = log_journal(supabase, "contact-1", "document_manquant", "Sujet test")
    assert jid == "journal-001"


def test_log_journal_error_returns_none():
    supabase = MagicMock()
    supabase.table.side_effect = Exception("DB error")
    jid = log_journal(supabase, "contact-1", "autre", "sujet")
    assert jid is None


# ─── run (intégration) ────────────────────────────────────────────────────────


def test_run_dry_run_no_db_write():
    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails") as mock_fetch,
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client") as _mock_sb,
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client") as _mock_ai,
        patch("apps.jmpartners.agents.mail_handler.identify_contact") as mock_id,
        patch("apps.jmpartners.agents.mail_handler.classify_request") as mock_clf,
        patch("apps.jmpartners.agents.mail_handler.log_journal") as mock_log,
    ):
        mock_fetch.return_value = [("mid-1", "test@example.com", "Test", "Corps")]
        mock_id.return_value = ("contact-1", "SARL Test")
        mock_clf.return_value = "document_manquant"
        mock_log.return_value = "journal-1"

        result = run(dry_run=True)

        assert result["traites"] == 1
        assert result["non_matches"] == 0
        assert result["emails"][0]["type_demande"] == "document_manquant"
        mock_log.assert_not_called()


def test_run_empty_inbox():
    with (
        patch("apps.jmpartners.agents.mail_handler.fetch_unseen_emails") as mock_fetch,
        patch("apps.jmpartners.agents.mail_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.mail_handler.get_anthropic_client"),
    ):
        mock_fetch.return_value = []
        result = run(dry_run=True)
        assert result["traites"] == 0
        assert result["non_matches"] == 0
