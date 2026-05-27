"""Tests pour apps.jmpartners.agents.tri_classification_agent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.tri_classification_agent import TriClassificationAgent


# ─── _classifier (tests unitaires purs) ──────────────────────────────────────


def test_classifier_facture_fournisseur():
    agent = TriClassificationAgent()
    contenu = {"siret": "12345678901234", "montant_ht": "100.00", "montant_ttc": "120.00"}
    type_piece, sous_type, score = agent._classifier(contenu)
    assert type_piece == "fournisseur"
    assert sous_type == "facture"
    assert score == 0.95


def test_classifier_releve_bancaire():
    agent = TriClassificationAgent()
    contenu = {"info": "RELEVÉ DE COMPTE", "compte_bancaire": "FR76 1234"}
    type_piece, sous_type, score = agent._classifier(contenu)
    assert type_piece == "banque"
    assert sous_type == "releve"
    assert score == 0.92


def test_classifier_social():
    agent = TriClassificationAgent()
    contenu = {"organisme": "URSSAF", "periode": "2026-04"}
    type_piece, sous_type, score = agent._classifier(contenu)
    assert type_piece == "social"
    assert sous_type == "declaration"
    assert score == 0.88


def test_classifier_fiscal():
    agent = TriClassificationAgent()
    contenu = {"reference": "CA3", "emetteur": "DGFiP"}
    type_piece, sous_type, score = agent._classifier(contenu)
    assert type_piece == "fiscal"
    assert sous_type == "declaration"
    assert score == 0.85


def test_classifier_ambigu():
    agent = TriClassificationAgent()
    contenu = {"texte": "document sans indication claire"}
    type_piece, sous_type, score = agent._classifier(contenu)
    assert type_piece == "autre"
    assert sous_type is None
    assert score == 0.40


# ─── run() ────────────────────────────────────────────────────────────────────


def test_run_liste_vide():
    agent = TriClassificationAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["documents_traites"] == 0
    assert result["qualifies_auto"] == 0
    assert result["en_attente"] == 0
    assert result["erreurs"] == []


def test_run_document_ids_filtre():
    """Seuls les IDs fournis sont traités (query .in_())."""
    agent = TriClassificationAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.in_.return_value.execute.return_value.data = [
        {
            "id": "doc-1",
            "contenu_extrait": {
                "siret": "12345678901234",
                "montant_ht": "200.00",
                "montant_ttc": "240.00",
            },
        }
    ]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run(document_ids=["doc-1"])

    assert result["documents_traites"] == 1
    assert result["qualifies_auto"] == 1
    assert result["details"][0]["document_id"] == "doc-1"
    assert result["details"][0]["type_piece"] == "fournisseur"
    assert result["details"][0]["statut"] == "qualifie"


def test_run_document_ambigu_en_attente():
    """Document avec score < 0.80 → statut en_attente_collaborateur."""
    agent = TriClassificationAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "doc-ambigu", "contenu_extrait": {"texte": "inconnu"}}
    ]

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["en_attente"] == 1
    assert result["qualifies_auto"] == 0
    assert result["details"][0]["statut"] == "en_attente_collaborateur"
    assert result["details"][0]["raison_attente"] == "score_confiance_insuffisant"


def test_run_erreur_supabase():
    """Erreur Supabase sur la lecture → loggée, agent retourne erreurs non vide."""
    agent = TriClassificationAgent()
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.side_effect = Exception(
        "DB connection lost"
    )

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["documents_traites"] == 0
    assert len(result["erreurs"]) == 1
    assert "DB connection lost" in result["erreurs"][0]
