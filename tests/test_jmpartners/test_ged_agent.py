"""Tests unitaires pour GEDAgent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.ged_agent import GEDAgent


def _make_doc(**kwargs: object) -> dict:
    base = {
        "id": "doc-001",
        "nom_fichier": "facture.pdf",
        "type_piece": "fournisseur",
        "date_reception": "2024-03-15T10:00:00",
        "dossier_id": "dossier-42",
        "chemin_stockage": None,
        "chemin_stockage_tmp": None,
        "statut": "valide",
    }
    base.update(kwargs)
    return base


def _make_supabase_mock(documents: list[dict], existing_archives_count: int = 0) -> MagicMock:
    sb = MagicMock()

    # documents query
    docs_resp = MagicMock()
    docs_resp.data = documents
    (
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value
    ) = docs_resp

    # archive count query (like)
    count_resp = MagicMock()
    count_resp.data = [{}] * existing_archives_count
    (
        sb.table.return_value.select.return_value.eq.return_value.like.return_value.execute.return_value
    ) = count_resp

    # update
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    # journaux insert
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

    # storage download
    sb.storage.from_.return_value.download.return_value = b"fake-content"
    # storage upload
    sb.storage.from_.return_value.upload.return_value = MagicMock()

    return sb


class TestGEDAgent:
    def test_document_valide_archive(self) -> None:
        doc = _make_doc()
        sb = _make_supabase_mock([doc])
        agent = GEDAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["documents_archives"] == 1
        assert len(result["details"]) == 1
        detail = result["details"][0]
        assert "dossier-42" in detail["chemin_archive"]
        assert "2024" in detail["chemin_archive"]
        assert "03" in detail["chemin_archive"]
        assert detail["statut"] == "archive"

    def test_document_en_attente_ignore(self) -> None:
        # Supabase query filters by statut="valide", so en_attente docs are never returned
        sb = _make_supabase_mock([])  # Supabase returns empty list
        agent = GEDAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["documents_archives"] == 0
        assert result["details"] == []

    def test_numerotation_sequentielle(self) -> None:
        doc = _make_doc()
        sb = _make_supabase_mock([doc], existing_archives_count=2)
        agent = GEDAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["documents_archives"] == 1
        detail = result["details"][0]
        # num_seq = 2 + 1 = 3 → formatted as 0003
        assert "0003_facture.pdf" in detail["chemin_archive"]
        assert detail["numero_sequentiel"] == 3

    def test_doublon_archive_ignore(self) -> None:
        # Document already has chemin_stockage set → considered already archived
        doc = _make_doc(chemin_stockage="dossier-42/2024/03/fournisseurs/0001_facture.pdf")
        sb = _make_supabase_mock([doc])
        agent = GEDAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert result["documents_archives"] == 0
        assert result["details"] == []

    def test_erreur_storage_agent_continue(self) -> None:
        doc1 = _make_doc(id="doc-001", nom_fichier="facture1.pdf")
        doc2 = _make_doc(id="doc-002", nom_fichier="facture2.pdf")

        sb = _make_supabase_mock([doc1, doc2])

        # First upload raises, second succeeds
        call_count = {"n": 0}
        original_upload = sb.storage.from_.return_value.upload

        def upload_side_effect(*args: object, **kwargs: object) -> MagicMock:
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("Storage unavailable")
            return MagicMock()

        sb.storage.from_.return_value.upload.side_effect = upload_side_effect

        agent = GEDAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run()

        assert len(result["erreurs"]) == 1
        assert "doc-001" in result["erreurs"][0]
        # Second document still processed
        assert result["documents_archives"] == 1
