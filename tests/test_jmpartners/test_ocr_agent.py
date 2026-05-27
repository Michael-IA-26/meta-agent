"""Tests pour apps.jmpartners.agents.ocr_agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.ocr_agent import OCRAgent


def _make_anthropic_mock(ocr_payload: dict) -> MagicMock:
    """Retourne un mock Anthropic dont .messages.create() renvoie le payload JSON."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(ocr_payload))]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def _make_supabase_mock(rows: list[dict], download_bytes: bytes = b"fake-image-data") -> MagicMock:
    """Retourne un mock Supabase configuré pour select + storage download."""
    mock_sb = MagicMock()
    # select().eq().execute().data
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows
    # storage.from_().download()
    mock_sb.storage.from_.return_value.download.return_value = download_bytes
    return mock_sb


def _make_supabase_mock_with_in(rows: list[dict], download_bytes: bytes = b"fake-image-data") -> MagicMock:
    """Retourne un mock Supabase configuré pour select + in_() + storage download."""
    mock_sb = MagicMock()
    # select().in_().execute().data
    mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = rows
    # storage.from_().download()
    mock_sb.storage.from_.return_value.download.return_value = download_bytes
    return mock_sb


# ─── test_run_liste_vide ──────────────────────────────────────────────────────


def test_run_liste_vide():
    """Aucun document en attente → documents_traites=0, pas d'erreur."""
    agent = OCRAgent()
    mock_sb = _make_supabase_mock(rows=[])
    mock_anthropic = _make_anthropic_mock({})

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 0
    assert result["documents_a_trier"] == 0
    assert result["documents_en_attente"] == 0
    assert result["erreurs"] == []
    assert result["details"] == []


# ─── test_run_document_score_eleve_a_trier ────────────────────────────────────


def test_run_document_score_eleve_a_trier():
    """score >= 0.70 → statut='a_trier', documents_a_trier=1."""
    agent = OCRAgent()
    ocr_payload = {
        "type_document": "facture_fournisseur",
        "montant_ht": 100.0,
        "montant_tva": 20.0,
        "montant_ttc": 120.0,
        "date_document": "2026-01-15",
        "tiers_nom": "Fournisseur SAS",
        "siret": "12345678901234",
        "compte_bancaire": None,
        "reference": "FAC-2026-001",
        "score_confiance": 0.92,
        "multi_factures": False,
        "fragments": [],
    }
    rows = [
        {
            "id": "doc-haute-confiance",
            "dossier_id": "dossier-1",
            "chemin_storage": "dossier-1/facture.jpg",
            "nom_fichier": "facture.jpg",
        }
    ]
    mock_sb = _make_supabase_mock(rows=rows)
    mock_anthropic = _make_anthropic_mock(ocr_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 1
    assert result["documents_a_trier"] == 1
    assert result["documents_en_attente"] == 0
    assert result["erreurs"] == []
    detail = result["details"][0]
    assert detail["document_id"] == "doc-haute-confiance"
    assert detail["statut"] == "a_trier"
    assert detail["raison_attente"] is None
    assert detail["score_detection"] == 0.92
    assert detail["type_document_detecte"] == "facture_fournisseur"


# ─── test_run_document_score_faible_en_attente ───────────────────────────────


def test_run_document_score_faible_en_attente():
    """score < 0.70 → statut='en_attente_collaborateur', raison_attente='score_ocr_insuffisant'."""
    agent = OCRAgent()
    ocr_payload = {
        "type_document": "autre",
        "montant_ht": None,
        "montant_tva": None,
        "montant_ttc": None,
        "date_document": None,
        "tiers_nom": None,
        "siret": None,
        "compte_bancaire": None,
        "reference": None,
        "score_confiance": 0.45,
        "multi_factures": False,
        "fragments": [],
    }
    rows = [
        {
            "id": "doc-faible-confiance",
            "dossier_id": None,
            "chemin_storage": "uploads/scan_illisible.png",
            "nom_fichier": "scan_illisible.png",
        }
    ]
    mock_sb = _make_supabase_mock(rows=rows)
    mock_anthropic = _make_anthropic_mock(ocr_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 1
    assert result["documents_a_trier"] == 0
    assert result["documents_en_attente"] == 1
    detail = result["details"][0]
    assert detail["statut"] == "en_attente_collaborateur"
    assert detail["raison_attente"] == "score_ocr_insuffisant"
    assert detail["score_detection"] == 0.45


# ─── test_run_multi_factures_multi_dossiers ───────────────────────────────────


def test_run_multi_factures_multi_dossiers():
    """multi_factures=True ET fragments non vide → multi_dossiers=True."""
    agent = OCRAgent()
    ocr_payload = {
        "type_document": "facture_fournisseur",
        "montant_ht": 500.0,
        "montant_tva": 100.0,
        "montant_ttc": 600.0,
        "date_document": "2026-03-01",
        "tiers_nom": "Multi Corp",
        "siret": "98765432100012",
        "compte_bancaire": None,
        "reference": "LOT-2026-042",
        "score_confiance": 0.85,
        "multi_factures": True,
        "fragments": [
            {"page": 1, "montant_ttc": 300.0},
            {"page": 2, "montant_ttc": 300.0},
        ],
    }
    rows = [
        {
            "id": "doc-multi",
            "dossier_id": "dossier-multi",
            "chemin_storage": "dossier-multi/lot.pdf",
            "nom_fichier": "lot.pdf",
        }
    ]
    mock_sb = _make_supabase_mock(rows=rows)
    mock_anthropic = _make_anthropic_mock(ocr_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 1
    detail = result["details"][0]
    assert detail["multi_dossiers"] is True
    assert len(detail["fragments"]) == 2
    assert detail["statut"] == "a_trier"


# ─── test_run_document_ids_filtre ─────────────────────────────────────────────


def test_run_document_ids_filtre():
    """Seuls les IDs fournis sont traités — la query utilise .in_()."""
    agent = OCRAgent()
    ocr_payload = {
        "type_document": "releve_bancaire",
        "montant_ht": None,
        "montant_tva": None,
        "montant_ttc": None,
        "date_document": "2026-02-28",
        "tiers_nom": None,
        "siret": None,
        "compte_bancaire": "FR76 1234 5678 9012",
        "reference": "REL-FEV-2026",
        "score_confiance": 0.80,
        "multi_factures": False,
        "fragments": [],
    }
    rows = [
        {
            "id": "doc-filtre-1",
            "dossier_id": "dossier-bank",
            "chemin_storage": "dossier-bank/releve.pdf",
            "nom_fichier": "releve.pdf",
        }
    ]
    mock_sb = _make_supabase_mock_with_in(rows=rows)
    mock_anthropic = _make_anthropic_mock(ocr_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run(document_ids=["doc-filtre-1"])

    # Vérifie que .in_() a bien été appelé
    mock_sb.table.return_value.select.return_value.in_.assert_called_once_with("id", ["doc-filtre-1"])

    assert result["documents_traites"] == 1
    assert result["details"][0]["document_id"] == "doc-filtre-1"


# ─── test_run_erreur_claude_api ───────────────────────────────────────────────


def test_run_erreur_claude_api():
    """Exception levée par l'API Anthropic → erreur loggée, agent continue."""
    agent = OCRAgent()
    rows = [
        {
            "id": "doc-erreur-claude",
            "dossier_id": None,
            "chemin_storage": "uploads/doc.jpg",
            "nom_fichier": "doc.jpg",
        }
    ]
    mock_sb = _make_supabase_mock(rows=rows)

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = Exception("API rate limit exceeded")

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 0
    assert len(result["erreurs"]) == 1
    assert "doc-erreur-claude" in result["erreurs"][0]
    assert "API rate limit exceeded" in result["erreurs"][0]


# ─── test_run_erreur_supabase_storage ─────────────────────────────────────────


def test_run_erreur_supabase_storage():
    """Exception lors du téléchargement Supabase Storage → erreur loggée, agent continue."""
    agent = OCRAgent()
    rows = [
        {
            "id": "doc-erreur-storage",
            "dossier_id": "dossier-x",
            "chemin_storage": "dossier-x/introuvable.pdf",
            "nom_fichier": "introuvable.pdf",
        }
    ]
    mock_sb = _make_supabase_mock(rows=rows)
    mock_sb.storage.from_.return_value.download.side_effect = Exception("Object not found")
    mock_anthropic = _make_anthropic_mock({})

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["documents_traites"] == 0
    assert len(result["erreurs"]) == 1
    assert "doc-erreur-storage" in result["erreurs"][0]
    assert "Object not found" in result["erreurs"][0]
