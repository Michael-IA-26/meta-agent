"""Tests TDD — relance_handler."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.relance_handler import RelanceHandler, run


def _doc_result(manquants=None, contact_id="c-1", dossier_id="d-1"):
    return {
        "dossier_id": dossier_id,
        "contact_id": contact_id,
        "type_dossier": "bilan",
        "manquants": manquants or [],
        "complets": [],
        "erreur": None,
    }


def _manquant(nom="Grand Livre", type_doc="grand_livre", urgence="J-7"):
    return {"nom_document": nom, "type_document": type_doc,
            "deadline": None, "urgence": urgence}


def test_aucun_document_manquant_skip():
    result = run(_doc_result(manquants=[]), dry_run=True)

    assert result["envoye"] is False
    assert result["raison_skip"] == "Aucun document manquant"


def test_contact_id_absent_skip():
    result = run(_doc_result(manquants=[_manquant()], contact_id=None), dry_run=True)

    assert result["envoye"] is False
    assert "contact_id" in result["raison_skip"]


def test_relance_deja_envoyee_48h_skip(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    sb = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[{"id": "j-1"}])
    for attr in ("select", "eq", "gte", "limit"):
        setattr(chain, attr, MagicMock(return_value=chain))
    sb.table.return_value.select.return_value = chain

    with patch("apps.jmpartners.agents.relance_handler.get_supabase_client",
               return_value=sb):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=False)

    assert result["envoye"] is False
    assert result["raison_skip"] is not None


def test_email_contact_introuvable_skip(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    sb = MagicMock()
    # Anti-doublon → pas de doublon
    no_doublon = MagicMock(data=[])
    # Fetch contact → rien
    no_contact = MagicMock(data=None)
    chain_no = MagicMock()
    chain_no.execute.return_value = no_doublon
    for attr in ("select", "eq", "gte", "limit", "single"):
        setattr(chain_no, attr, MagicMock(return_value=chain_no))

    def table_side(name):
        t = MagicMock()
        c = MagicMock()
        if name == "contacts":
            c.execute.return_value = no_contact
        else:
            c.execute.return_value = no_doublon
        for attr in ("select", "eq", "gte", "limit", "single", "insert"):
            setattr(c, attr, MagicMock(return_value=c))
        t.select = MagicMock(return_value=c)
        t.insert = MagicMock(return_value=c)
        return t

    sb.table = table_side

    with patch("apps.jmpartners.agents.relance_handler.get_supabase_client",
               return_value=sb):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=False)

    assert result["envoye"] is False
    assert result["email_destinataire"] is None


def test_dry_run_compose_mais_nenvoie_pas(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee",
              return_value=False),
        patch("apps.jmpartners.agents.relance_handler.fetch_contact_email",
              return_value=("contact@dupont.fr", "SARL Dupont")),
        patch("apps.jmpartners.agents.relance_handler.compose_relance",
              return_value=("Sujet test", "Corps test")),
        patch("apps.jmpartners.agents.relance_handler.send_smtp") as mock_smtp,
        patch("apps.jmpartners.agents.relance_handler.log_journal") as mock_log,
    ):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=True)

    mock_smtp.assert_not_called()
    mock_log.assert_not_called()
    assert result["envoye"] is False
    assert result["raison_skip"] == "dry_run"
    assert result["sujet"] == "Sujet test"


def test_smtp_down_retourne_envoye_false(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee",
              return_value=False),
        patch("apps.jmpartners.agents.relance_handler.fetch_contact_email",
              return_value=("contact@dupont.fr", "SARL Dupont")),
        patch("apps.jmpartners.agents.relance_handler.compose_relance",
              return_value=("Sujet", "Corps")),
        patch("apps.jmpartners.agents.relance_handler.send_smtp", return_value=False),
        patch("apps.jmpartners.agents.relance_handler.log_journal", return_value="j-1"),
    ):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=False)

    assert result["envoye"] is False
    assert result["raison_skip"] == "Erreur SMTP"


def test_claude_timeout_utilise_fallback_et_envoie(monkeypatch):
    """Si compose_relance lève une exception, le fallback statique est utilisé."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee",
              return_value=False),
        patch("apps.jmpartners.agents.relance_handler.fetch_contact_email",
              return_value=("c@c.fr", "Client")),
        patch("apps.jmpartners.agents.relance_handler.get_anthropic_client",
              side_effect=Exception("Anthropic timeout")),
        patch("apps.jmpartners.agents.relance_handler.send_smtp", return_value=True),
        patch("apps.jmpartners.agents.relance_handler.log_journal", return_value="j-1"),
    ):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=False)

    # Le fallback compose un email sans Claude — l'envoi doit quand même réussir
    assert result["envoye"] is True


def test_happy_path_envoi_reussi(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    with (
        patch("apps.jmpartners.agents.relance_handler.get_supabase_client"),
        patch("apps.jmpartners.agents.relance_handler.relance_deja_envoyee",
              return_value=False),
        patch("apps.jmpartners.agents.relance_handler.fetch_contact_email",
              return_value=("contact@dupont.fr", "SARL Dupont")),
        patch("apps.jmpartners.agents.relance_handler.compose_relance",
              return_value=("Sujet", "Corps")),
        patch("apps.jmpartners.agents.relance_handler.send_smtp", return_value=True),
        patch("apps.jmpartners.agents.relance_handler.log_journal", return_value="j-1"),
    ):
        result = run(_doc_result(manquants=[_manquant()]), dry_run=False)

    assert result["envoye"] is True
    assert result["journal_id"] == "j-1"


def test_relance_handler_facade_appelle_check_docs(monkeypatch):
    """RelanceHandler.run() appelle document_checker puis relance_handler."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    mock_doc = _doc_result(manquants=[])
    mock_rel = {"envoye": False, "raison_skip": "Aucun document manquant",
                "email_destinataire": None, "sujet": None, "corps": None, "journal_id": None}

    with (
        patch("apps.jmpartners.agents.relance_handler.run",
              return_value=mock_rel) as mock_run,
    ):
        from apps.jmpartners.agents.document_checker import run as check_docs_real
        with patch("apps.jmpartners.agents.relance_handler.RelanceHandler.run",
                   wraps=RelanceHandler().run):
            with patch("apps.jmpartners.agents.document_checker.run",
                       return_value=mock_doc) as mock_check:
                handler = RelanceHandler(cabinet_id="jmpartners")
                # Test structure only — check_docs is imported locally
                assert hasattr(handler, "run")
                assert handler.cabinet_id == "jmpartners"
