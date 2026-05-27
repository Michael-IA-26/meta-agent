"""Tests pour apps.jmpartners.agents.miroir_sage_agent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent

# ─── FEC CSV fixtures ─────────────────────────────────────────────────────────

FEC_3_ROWS = (
    "JournalCode;EcritureDate;CompteNum;CompteLib;Debit;Credit;EcritureLib;PieceRef\n"
    "ACH;20240101;401000;Fournisseur A;1000,00;0,00;FACTURE FOURNISSEUR;F001\n"
    "VTE;20240102;411000;Client B;0,00;2000,00;VENTE PRODUIT;V001\n"
    "BQ;20240103;512000;Banque;500,00;0,00;VIREMENT;REF003\n"
)

FEC_PAIE_ROW = (
    "JournalCode;EcritureDate;CompteNum;CompteLib;Debit;Credit;EcritureLib;PieceRef\n"
    "PAI;20240115;641000;Salaires;5000,00;0,00;PAIE JUILLET;P001\n"
)

FEC_681_ROW = (
    "JournalCode;EcritureDate;CompteNum;CompteLib;Debit;Credit;EcritureLib;PieceRef\n"
    "OD;20240120;681000;Dotations;300,00;0,00;DOTATION AMORTISSEMENT;OD001\n"
)


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_mock_supabase(existing_hash_data: list | None = None) -> MagicMock:
    """Build a Supabase mock with chainable builder pattern."""
    mock_sb = MagicMock()

    # storage.from_().download()
    mock_sb.storage.from_.return_value.download.return_value = FEC_3_ROWS.encode("utf-8")

    # syncs_sage hash check: .table().select().eq().execute()
    hash_check_exec = MagicMock()
    hash_check_exec.data = existing_hash_data if existing_hash_data is not None else []

    mock_table = MagicMock()
    mock_table.select.return_value.eq.return_value.execute.return_value = hash_check_exec

    # insert chains return a MagicMock with .execute()
    mock_table.insert.return_value.execute.return_value = MagicMock(data=[])

    mock_sb.table.return_value = mock_table

    return mock_sb


# ─── Tests sync_fec ───────────────────────────────────────────────────────────


def test_sync_fec_nouvelles_lignes() -> None:
    """FEC CSV with 3 rows, no existing hash → ecritures_nouvelles=3."""
    agent = MiroirSageAgent()
    mock_sb = _make_mock_supabase(existing_hash_data=[])
    mock_sb.storage.from_.return_value.download.return_value = FEC_3_ROWS.encode("utf-8")
    agent._supabase = mock_sb  # type: ignore[assignment]

    result = agent._sync_fec()

    assert result["ecritures_nouvelles"] == 3
    assert result["ecritures_importees"] == 3
    assert result["date_sync"] != ""


def test_sync_fec_fichier_deja_synced() -> None:
    """Existing hash in syncs_sage → ecritures_nouvelles=0."""
    agent = MiroirSageAgent()
    mock_sb = _make_mock_supabase(existing_hash_data=[{"id": "existing-sync-1"}])
    mock_sb.storage.from_.return_value.download.return_value = FEC_3_ROWS.encode("utf-8")
    agent._supabase = mock_sb  # type: ignore[assignment]

    result = agent._sync_fec()

    assert result["ecritures_nouvelles"] == 0
    assert result["ecritures_importees"] == 0


def test_sync_fec_flag_source_paie() -> None:
    """Row with EcritureLib='PAIE JUILLET' → source='paie' in INSERT."""
    agent = MiroirSageAgent()

    inserted_rows: list[list[dict]] = []

    mock_sb = MagicMock()
    mock_sb.storage.from_.return_value.download.return_value = FEC_PAIE_ROW.encode("utf-8")

    # Hash check → empty (no existing hash)
    hash_exec = MagicMock()
    hash_exec.data = []
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = (
        hash_exec
    )

    # Capture insert calls
    def capture_insert(rows):  # type: ignore[no-untyped-def]
        inserted_rows.append(rows)
        return MagicMock(execute=MagicMock(return_value=MagicMock(data=[])))

    mock_sb.table.return_value.insert.side_effect = capture_insert

    agent._supabase = mock_sb  # type: ignore[assignment]

    result = agent._sync_fec()

    # Find the ecritures_sage insert (first insert call, contains the rows)
    assert result["ecritures_nouvelles"] == 1
    ecriture_insert = inserted_rows[0]
    assert isinstance(ecriture_insert, list)
    assert len(ecriture_insert) == 1
    assert ecriture_insert[0]["source"] == "paie"


# ─── Tests rapport_matinal ────────────────────────────────────────────────────


def test_rapport_matinal_email_envoye() -> None:
    """1 collaborateur, mock Claude returns text, mock send_email returns True → collaborateurs_notifies=1."""
    agent = MiroirSageAgent()

    mock_sb = MagicMock()

    # collaborateurs
    mock_sb.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "collab-1", "email": "collab@cabinet.fr", "nom": "Alice Martin"}
    ]
    # dossiers per collaborateur
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # ecritures_sage last 24h
    mock_sb.table.return_value.select.return_value.gte.return_value.execute.return_value.data = []
    # revision en_attente
    # journaux last 24h
    # echeances today

    # Build layered mock for multiple table queries
    def table_side_effect(name: str) -> MagicMock:  # type: ignore[return]
        t = MagicMock()
        t.select.return_value.execute.return_value.data = []
        t.select.return_value.eq.return_value.execute.return_value.data = []
        t.select.return_value.gte.return_value.execute.return_value.data = []
        if name == "collaborateurs":
            t.select.return_value.execute.return_value.data = [
                {"id": "collab-1", "email": "collab@cabinet.fr", "nom": "Alice Martin"}
            ]
        return t

    mock_sb.table.side_effect = table_side_effect
    agent._supabase = mock_sb  # type: ignore[assignment]

    # Mock Claude
    mock_anthropic = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Rapport matinal généré."
    mock_anthropic.messages.create.return_value.content = [mock_content]
    agent._anthropic = mock_anthropic  # type: ignore[assignment]

    with patch(
        "apps.jmpartners.agents.miroir_sage_agent.send_email", return_value=True
    ) as mock_email:
        result = agent._envoyer_rapport_matinal()

    assert result["collaborateurs_notifies"] == 1
    mock_email.assert_called_once()


def test_rapport_matinal_smtp_absent() -> None:
    """send_email returns False → collaborateurs_notifies=0, no exception."""
    agent = MiroirSageAgent()

    def table_side_effect(name: str) -> MagicMock:  # type: ignore[return]
        t = MagicMock()
        t.select.return_value.execute.return_value.data = []
        t.select.return_value.eq.return_value.execute.return_value.data = []
        t.select.return_value.gte.return_value.execute.return_value.data = []
        if name == "collaborateurs":
            t.select.return_value.execute.return_value.data = [
                {"id": "collab-1", "email": "collab@cabinet.fr", "nom": "Bob Dupont"}
            ]
        return t

    mock_sb = MagicMock()
    mock_sb.table.side_effect = table_side_effect
    agent._supabase = mock_sb  # type: ignore[assignment]

    mock_anthropic = MagicMock()
    mock_content = MagicMock()
    mock_content.text = "Rapport."
    mock_anthropic.messages.create.return_value.content = [mock_content]
    agent._anthropic = mock_anthropic  # type: ignore[assignment]

    with patch(
        "apps.jmpartners.agents.miroir_sage_agent.send_email", return_value=False
    ):
        result = agent._envoyer_rapport_matinal()

    assert result["collaborateurs_notifies"] == 0
    # No exception raised
