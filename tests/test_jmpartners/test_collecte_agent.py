"""Tests pour apps.jmpartners.agents.collecte_agent."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.collecte_agent import CollecteAgent, DocumentCollecte


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _fake_doc(message_id: str = "mock-outlook-test.pdf") -> DocumentCollecte:
    return DocumentCollecte(
        source="outlook",
        nom_fichier="test.pdf",
        contenu_binaire=b"%PDF fake",
        message_id=message_id,
        expediteur=None,
        date_reception="2026-05-27T00:00:00+00:00",
        dossier_id_hint=None,
    )


def _mock_supabase_no_duplicate() -> MagicMock:
    """Supabase mock : aucun doublon, storage et insert OK."""
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    return mock


def _mock_supabase_duplicate() -> MagicMock:
    """Supabase mock : doublon détecté."""
    mock = MagicMock()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "existing-doc"}
    ]
    return mock


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_run_source_outlook_mock_dir_absent():
    agent = CollecteAgent()
    with patch.dict("os.environ", {"OUTLOOK_MOCK_DIR": ""}):
        # Reload module-level constant via patching the module var
        with patch("apps.jmpartners.agents.collecte_agent.OUTLOOK_MOCK_DIR", ""):
            result = agent.run(sources=["outlook"])
    assert result["documents_recus"] == 0
    assert result["erreurs"] == []


def test_run_doublon_message_id_ignore():
    agent = CollecteAgent()
    doc = _fake_doc()
    mock_sb = _mock_supabase_duplicate()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        with patch.object(agent, "_collecter_outlook", return_value=[doc]):
            result = agent.run(sources=["outlook"])

    assert result["documents_recus"] == 1
    assert result["documents_dedupliques"] == 1
    assert result["documents_uploades"] == 0


def test_run_upload_reussi():
    agent = CollecteAgent()
    doc = _fake_doc()
    mock_sb = _mock_supabase_no_duplicate()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        with patch.object(agent, "_collecter_outlook", return_value=[doc]):
            result = agent.run(sources=["outlook"])

    assert result["documents_uploades"] == 1
    assert result["documents_dedupliques"] == 0
    assert result["erreurs"] == []


def test_run_source_inconnue():
    agent = CollecteAgent()
    result = agent.run(sources=["source_inconnue"])
    assert len(result["erreurs"]) == 1
    assert "Source inconnue" in result["erreurs"][0]


def test_run_sources_filtre():
    """run(sources=["manuel"]) ne doit pas appeler _collecter_outlook."""
    agent = CollecteAgent()
    with patch.object(agent, "_collecter_outlook") as mock_outlook:
        result = agent.run(sources=["manuel"])
    mock_outlook.assert_not_called()
    assert result["documents_recus"] == 0
    assert result["erreurs"] == []


def test_run_erreur_supabase_upload():
    agent = CollecteAgent()
    doc = _fake_doc()
    mock_sb = MagicMock()
    # Pas de doublon
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # Erreur au storage upload
    mock_sb.storage.from_.return_value.upload.side_effect = Exception("storage error")

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        with patch.object(agent, "_collecter_outlook", return_value=[doc]):
            result = agent.run(sources=["outlook"])

    assert result["documents_uploades"] == 0
    assert len(result["erreurs"]) == 1
    assert "storage error" in result["erreurs"][0]


def test_run_outlook_lit_fichiers_pdf(tmp_path):
    """Vérifie que _collecter_outlook lit les .pdf depuis le mock dir."""
    pdf_file = tmp_path / "facture.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    agent = CollecteAgent()
    mock_sb = _mock_supabase_no_duplicate()

    with patch("apps.jmpartners.agents.collecte_agent.OUTLOOK_MOCK_DIR", str(tmp_path)):
        with patch.object(agent, "_get_supabase", return_value=mock_sb):
            result = agent.run(sources=["outlook"])

    assert result["documents_recus"] == 1
    assert result["documents"][0]["nom_fichier"] == "facture.pdf"
    assert result["documents"][0]["source"] == "outlook"
