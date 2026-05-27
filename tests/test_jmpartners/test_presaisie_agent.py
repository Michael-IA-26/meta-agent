"""Tests pour apps.jmpartners.agents.presaisie_agent."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import anthropic

from apps.jmpartners.agents.presaisie_agent import PresaisieAgent

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_anthropic_mock(ecritures_payload: list[dict]) -> MagicMock:
    """Retourne un mock Anthropic dont .messages.create() renvoie le payload JSON."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text=json.dumps(ecritures_payload))]
    mock_client.messages.create.return_value = mock_response
    return mock_client


def _make_supabase_mock(docs: list[dict]) -> MagicMock:
    """Retourne un mock Supabase basique pour la lecture de documents qualifiés."""
    mock_sb = MagicMock()
    # table("documents").select("*").eq("statut","qualifie").execute().data
    (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .execute.return_value
        .data
    ) = docs
    # table("ecritures").insert(...).execute()
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    # table("documents").update(...).eq(...).execute()
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    # RPC fallback — renvoie []
    mock_sb.rpc.return_value.execute.return_value.data = []
    return mock_sb


def _make_supabase_mock_with_ids(docs: list[dict]) -> MagicMock:
    """Mock Supabase pour requêtes avec in_() (document_ids fournis)."""
    mock_sb = MagicMock()
    # table("documents").select("*").in_("id", [...]).execute().data
    (
        mock_sb.table.return_value
        .select.return_value
        .in_.return_value
        .execute.return_value
        .data
    ) = docs
    mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = []
    return mock_sb


# ─── test_facture_fournisseur_simple ─────────────────────────────────────────


def test_facture_fournisseur_simple() -> None:
    """Claude retourne écriture ACH avec compte 401/606xxx → ecritures_proposees >= 1."""
    doc = {
        "id": "doc-001",
        "statut": "qualifie",
        "contenu_extrait": {
            "type_document": "facture_fournisseur",
            "montant_ht": 100.0,
            "montant_tva": 20.0,
            "montant_ttc": 120.0,
            "tiers_nom": "Fournisseur SA",
        },
    }
    ecriture_payload = [
        {
            "journal": "ACH",
            "compte_debit": "606100",
            "compte_credit": "401000",
            "tiers": "Fournisseur SA",
            "libelle": "Achat fournitures",
            "montant_ht": 100.0,
            "montant_tva": 20.0,
            "montant_ttc": 120.0,
            "taux_tva": 20.0,
            "source_validation": "regle_comptable",
        }
    ]

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])
    mock_anthropic = _make_anthropic_mock(ecriture_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["ecritures_proposees"] >= 1
    assert result["documents_traites"] == 1
    assert len(result["details"]) == 1
    ecriture = result["details"][0]["ecritures"][0]
    assert ecriture["journal"] == "ACH"
    assert "401" in ecriture["compte_credit"] or "401" in ecriture["compte_debit"]


# ─── test_autoliquidation_btp ─────────────────────────────────────────────────


def test_autoliquidation_btp() -> None:
    """contenu_extrait contient 'autoliquidation', Claude retourne comptes 44562/44566."""
    doc = {
        "id": "doc-002",
        "statut": "qualifie",
        "contenu_extrait": {
            "type_document": "facture_fournisseur",
            "mention": "autoliquidation TVA BTP",
            "montant_ht": 500.0,
            "montant_tva": 0.0,
            "montant_ttc": 500.0,
        },
    }
    ecriture_payload = [
        {
            "journal": "ACH",
            "compte_debit": "44562",
            "compte_credit": "44566",
            "tiers": None,
            "libelle": "Autoliquidation TVA BTP",
            "montant_ht": 500.0,
            "montant_tva": 0.0,
            "montant_ttc": 500.0,
            "taux_tva": None,
            "source_validation": "regle_comptable",
        }
    ]

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])
    mock_anthropic = _make_anthropic_mock(ecriture_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["ecritures_proposees"] >= 1
    ecriture = result["details"][0]["ecritures"][0]
    comptes = {ecriture["compte_debit"], ecriture["compte_credit"]}
    assert "44562" in comptes
    assert "44566" in comptes


# ─── test_restauration_taux_reduit ───────────────────────────────────────────


def test_restauration_taux_reduit() -> None:
    """Claude retourne taux_tva=10.0 → vérifier taux dans écriture."""
    doc = {
        "id": "doc-003",
        "statut": "qualifie",
        "contenu_extrait": {
            "type_document": "facture_fournisseur",
            "activite": "restauration sur place",
            "montant_ht": 90.91,
            "montant_tva": 9.09,
            "montant_ttc": 100.0,
        },
    }
    ecriture_payload = [
        {
            "journal": "ACH",
            "compte_debit": "625100",
            "compte_credit": "401000",
            "tiers": None,
            "libelle": "Repas restauration",
            "montant_ht": 90.91,
            "montant_tva": 9.09,
            "montant_ttc": 100.0,
            "taux_tva": 10.0,
            "source_validation": "regle_comptable",
        }
    ]

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])
    mock_anthropic = _make_anthropic_mock(ecriture_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    assert result["ecritures_proposees"] >= 1
    ecriture = result["details"][0]["ecritures"][0]
    assert ecriture["taux_tva"] == 10.0


# ─── test_pgvector_historique_retourne_fec_reconnu ───────────────────────────


def test_pgvector_historique_retourne_fec_reconnu() -> None:
    """mock _fetch_historique_similaire retourne données → source_validation='fec_reconnu'."""
    doc = {
        "id": "doc-004",
        "statut": "qualifie",
        "contenu_extrait": {
            "type_document": "facture_fournisseur",
            "tiers_nom": "EDF",
            "montant_ttc": 240.0,
        },
    }
    historique_fec = [
        {
            "journal": "ACH",
            "compte_debit": "606200",
            "compte_credit": "401000",
            "libelle": "EDF électricité",
            "taux_tva": 20.0,
        }
    ]
    ecriture_payload = [
        {
            "journal": "ACH",
            "compte_debit": "606200",
            "compte_credit": "401000",
            "tiers": "EDF",
            "libelle": "EDF électricité",
            "montant_ht": 200.0,
            "montant_tva": 40.0,
            "montant_ttc": 240.0,
            "taux_tva": 20.0,
            "source_validation": "fec_reconnu",
        }
    ]

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])
    mock_anthropic = _make_anthropic_mock(ecriture_payload)

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic), \
         patch.object(agent, "_fetch_historique_similaire", return_value=historique_fec):
        result = agent.run()

    assert result["ecritures_proposees"] >= 1
    ecriture = result["details"][0]["ecritures"][0]
    assert ecriture["source_validation"] == "fec_reconnu"


# ─── test_erreur_claude_api_degradation_gracieuse ────────────────────────────


def test_erreur_claude_api_degradation_gracieuse() -> None:
    """Anthropic exception → source_validation='a_verifier' dans le résultat, pas d'exception levée."""
    doc = {
        "id": "doc-005",
        "statut": "qualifie",
        "contenu_extrait": {"type_document": "facture_fournisseur"},
    }

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])

    mock_anthropic = MagicMock()
    mock_anthropic.messages.create.side_effect = anthropic.APIConnectionError(
        request=MagicMock()
    )

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    # Pas d'exception levée
    assert result["documents_traites"] == 1
    assert result["ecritures_proposees"] >= 1
    ecriture = result["details"][0]["ecritures"][0]
    assert ecriture["source_validation"] == "a_verifier"


# ─── test_erreur_supabase_loggee_agent_continue ──────────────────────────────


def test_erreur_supabase_loggee_agent_continue() -> None:
    """Supabase INSERT exception → erreur dans erreurs, agent ne crash pas."""
    doc = {
        "id": "doc-006",
        "statut": "qualifie",
        "contenu_extrait": {"type_document": "facture_fournisseur", "montant_ttc": 120.0},
    }
    ecriture_payload = [
        {
            "journal": "ACH",
            "compte_debit": "606100",
            "compte_credit": "401000",
            "tiers": None,
            "libelle": "Test achat",
            "montant_ht": 100.0,
            "montant_tva": 20.0,
            "montant_ttc": 120.0,
            "taux_tva": 20.0,
            "source_validation": "regle_comptable",
        }
    ]

    agent = PresaisieAgent()
    mock_sb = _make_supabase_mock([doc])
    mock_anthropic = _make_anthropic_mock(ecriture_payload)

    # INSERT lève une exception
    mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception(
        "Supabase INSERT error"
    )

    with patch.object(agent, "_get_supabase", return_value=mock_sb), \
         patch.object(agent, "_get_anthropic", return_value=mock_anthropic):
        result = agent.run()

    # L'agent ne crash pas
    assert result["documents_traites"] == 1
    # L'erreur est loggée dans erreurs
    assert len(result["erreurs"]) >= 1
    assert any("doc-006" in e for e in result["erreurs"])
