"""Tests pour apps.jmpartners.agents.verificateur_agent."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.jmpartners.agents.verificateur_agent import VerificateurAgent

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_supabase_mock(
    ecritures: list[dict] | None = None,
    ecritures_sage: list[dict] | None = None,
) -> MagicMock:
    """Construit un mock Supabase dont les appels .table() retournent les données voulues."""
    mock_sb = MagicMock()

    def table_side_effect(table_name: str) -> MagicMock:
        tbl = MagicMock()

        if table_name == "ecritures":
            # Chaîne de méthodes pour SELECT
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.in_.return_value = select_chain
            execute_resp = MagicMock()
            execute_resp.data = ecritures if ecritures is not None else []
            select_chain.execute.return_value = execute_resp

            tbl.select.return_value = select_chain

            # UPDATE (badge_anomalie)
            update_chain = MagicMock()
            update_chain.eq.return_value = update_chain
            update_chain.execute.return_value = MagicMock()
            tbl.update.return_value = update_chain

        elif table_name == "ecritures_sage":
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            execute_resp = MagicMock()
            execute_resp.data = ecritures_sage if ecritures_sage is not None else []
            select_chain.execute.return_value = execute_resp
            tbl.select.return_value = select_chain

        elif table_name == "journaux":
            insert_chain = MagicMock()
            insert_chain.execute.return_value = MagicMock()
            tbl.insert.return_value = insert_chain

        else:
            tbl.select.return_value = tbl
            tbl.eq.return_value = tbl
            tbl.in_.return_value = tbl
            tbl.update.return_value = tbl
            tbl.insert.return_value = tbl
            tbl.execute.return_value = MagicMock(data=[])

        return tbl

    mock_sb.table.side_effect = table_side_effect
    return mock_sb


# ─── Tests ───────────────────────────────────────────────────────────────────


def test_desequilibre_dc_bloquant() -> None:
    """Débit 100 != Crédit 80 → anomalie desequilibre_dc bloquante, lot_propre=False."""
    ecritures = [
        {
            "id": "ecr-1",
            "statut": "a_valider",
            "montant_debit": 100.0,
            "montant_credit": 0.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 100.0,
            "tiers": "FOURNISSEUR_A",
            "date_ecriture": "2026-05-01",
            "document_id": "doc-1",
        },
        {
            "id": "ecr-2",
            "statut": "a_valider",
            "montant_debit": 0.0,
            "montant_credit": 80.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 80.0,
            "tiers": "FOURNISSEUR_A",
            "date_ecriture": "2026-05-02",
            "document_id": "doc-1",
        },
    ]
    mock_sb = _make_supabase_mock(ecritures=ecritures, ecritures_sage=[])
    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["ecritures_verifiees"] == 2
    assert result["lot_propre"] is False

    types_anomalies = [a["type_anomalie"] for a in result["anomalies"]]
    assert "desequilibre_dc" in types_anomalies

    bloquantes = [a for a in result["anomalies"] if a["type_anomalie"] == "desequilibre_dc"]
    assert len(bloquantes) == 1
    assert bloquantes[0]["severite"] == "bloquante"


def test_compte_7xxx_debit_avertissement() -> None:
    """Compte compte_debit='700000' (produit) au débit → anomalie compte_incoherent avertissement."""
    ecritures = [
        {
            "id": "ecr-3",
            "statut": "a_valider",
            "montant_debit": 500.0,
            "montant_credit": 500.0,
            "compte_debit": "700000",
            "compte_credit": "411000",
            "montant_ttc": 500.0,
            "tiers": "CLIENT_B",
            "date_ecriture": "2026-05-10",
            "document_id": "doc-2",
        },
    ]
    mock_sb = _make_supabase_mock(ecritures=ecritures, ecritures_sage=[])
    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    types_anomalies = [a["type_anomalie"] for a in result["anomalies"]]
    assert "compte_incoherent" in types_anomalies

    incoherents = [a for a in result["anomalies"] if a["type_anomalie"] == "compte_incoherent"]
    assert len(incoherents) == 1
    assert incoherents[0]["severite"] == "avertissement"
    assert incoherents[0]["ecriture_id"] == "ecr-3"


def test_doublon_detecte_ecritures_sage() -> None:
    """ecritures_sage contient même montant+tiers+date → anomalie doublon."""
    ecritures = [
        {
            "id": "ecr-4",
            "statut": "a_valider",
            "montant_debit": 200.0,
            "montant_credit": 200.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 200.0,
            "tiers": "FOURNISSEUR_C",
            "date_ecriture": "2026-04-15",
            "document_id": "doc-3",
        },
    ]
    ecritures_sage = [
        {
            "id": "sage-1",
            "montant_ttc": 200.0,
            "tiers": "FOURNISSEUR_C",
            "date_ecriture": "2026-04-15",
        },
    ]

    # Pour ce test on a besoin d'un mock plus précis sur ecritures_sage
    mock_sb = MagicMock()

    def table_side_effect(table_name: str) -> MagicMock:
        tbl = MagicMock()

        if table_name == "ecritures":
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.in_.return_value = select_chain
            execute_resp = MagicMock()
            execute_resp.data = ecritures
            select_chain.execute.return_value = execute_resp
            tbl.select.return_value = select_chain

            update_chain = MagicMock()
            update_chain.eq.return_value = update_chain
            update_chain.execute.return_value = MagicMock()
            tbl.update.return_value = update_chain

        elif table_name == "ecritures_sage":
            # Première requête (montant_ttc de tiers) → vide (aucun sage pour moyenne)
            # Deuxième requête (doublon) → retourne la donnée
            select_chain = MagicMock()

            # select("montant_ttc") pour la moyenne → renvoyer []
            # select("id") pour les doublons → renvoyer sage data
            def _select(fields: str) -> MagicMock:
                chain = MagicMock()
                chain.eq.return_value = chain

                if fields == "id":
                    # doublon check
                    resp = MagicMock()
                    resp.data = ecritures_sage
                    chain.execute.return_value = resp
                else:
                    # moyenne tiers
                    resp = MagicMock()
                    resp.data = []
                    chain.execute.return_value = resp

                return chain

            tbl.select.side_effect = _select

        elif table_name == "journaux":
            insert_chain = MagicMock()
            insert_chain.execute.return_value = MagicMock()
            tbl.insert.return_value = insert_chain

        return tbl

    mock_sb.table.side_effect = table_side_effect
    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    types_anomalies = [a["type_anomalie"] for a in result["anomalies"]]
    assert "doublon" in types_anomalies

    doublons = [a for a in result["anomalies"] if a["type_anomalie"] == "doublon"]
    assert len(doublons) == 1
    assert doublons[0]["ecriture_id"] == "ecr-4"
    assert doublons[0]["severite"] == "avertissement"


def test_lot_sans_anomalie_propre() -> None:
    """Débit/crédit équilibrés, comptes normaux, pas de doublon → lot_propre=True, anomalies=[]."""
    ecritures = [
        {
            "id": "ecr-5",
            "statut": "a_valider",
            "montant_debit": 300.0,
            "montant_credit": 0.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 300.0,
            "tiers": "FOURNISSEUR_D",
            "date_ecriture": "2026-05-20",
            "document_id": "doc-4",
        },
        {
            "id": "ecr-6",
            "statut": "a_valider",
            "montant_debit": 0.0,
            "montant_credit": 300.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 300.0,
            "tiers": "FOURNISSEUR_D",
            "date_ecriture": "2026-05-20",
            "document_id": "doc-4",
        },
    ]
    mock_sb = _make_supabase_mock(ecritures=ecritures, ecritures_sage=[])
    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    assert result["lot_propre"] is True
    assert result["anomalies"] == []
    assert result["ecritures_verifiees"] == 2


def test_document_ids_filtre() -> None:
    """document_ids fournis → la requête Supabase filtre par document_id."""
    ecritures = [
        {
            "id": "ecr-7",
            "statut": "a_valider",
            "montant_debit": 50.0,
            "montant_credit": 50.0,
            "compte_debit": "600000",
            "compte_credit": "401000",
            "montant_ttc": 50.0,
            "tiers": "FOURNISSEUR_E",
            "date_ecriture": "2026-05-25",
            "document_id": "doc-42",
        },
    ]

    # On capture les appels réels sur la chaîne .select().eq().in_()
    mock_sb = MagicMock()
    select_chain = MagicMock()
    select_chain.eq.return_value = select_chain
    in_chain = MagicMock()
    execute_resp = MagicMock()
    execute_resp.data = ecritures
    in_chain.execute.return_value = execute_resp
    select_chain.in_.return_value = in_chain

    ecritures_tbl = MagicMock()
    ecritures_tbl.select.return_value = select_chain
    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock()
    ecritures_tbl.update.return_value = update_chain

    sage_tbl = MagicMock()
    sage_select = MagicMock()
    sage_select.eq.return_value = sage_select
    sage_resp = MagicMock()
    sage_resp.data = []
    sage_select.execute.return_value = sage_resp
    sage_tbl.select.return_value = sage_select

    journaux_tbl = MagicMock()
    journaux_insert = MagicMock()
    journaux_insert.execute.return_value = MagicMock()
    journaux_tbl.insert.return_value = journaux_insert

    def table_side_effect(table_name: str) -> MagicMock:
        if table_name == "ecritures":
            return ecritures_tbl
        if table_name == "ecritures_sage":
            return sage_tbl
        if table_name == "journaux":
            return journaux_tbl
        return MagicMock()

    mock_sb.table.side_effect = table_side_effect

    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run(document_ids=["doc-42"])

    # Vérifie que .in_ a bien été appelé avec le filtre document_id
    select_chain.in_.assert_called_once_with("document_id", ["doc-42"])
    assert result["ecritures_verifiees"] == 1


def test_jamais_correction_auto() -> None:
    """L'agent ne modifie jamais montant_ht, montant_ttc, compte_debit, compte_credit."""
    ecritures = [
        {
            "id": "ecr-8",
            "statut": "a_valider",
            "montant_debit": 150.0,
            "montant_credit": 150.0,
            "compte_debit": "700000",  # produit au débit → anomalie compte_incoherent
            "compte_credit": "401000",
            "montant_ttc": 150.0,
            "tiers": "CLIENT_F",
            "date_ecriture": "2026-05-26",
            "document_id": "doc-5",
        },
    ]

    update_calls: list[dict] = []

    mock_sb = MagicMock()

    def table_side_effect(table_name: str) -> MagicMock:
        tbl = MagicMock()

        if table_name == "ecritures":
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            select_chain.in_.return_value = select_chain
            execute_resp = MagicMock()
            execute_resp.data = ecritures
            select_chain.execute.return_value = execute_resp
            tbl.select.return_value = select_chain

            def capture_update(payload: dict) -> MagicMock:
                update_calls.append(payload)
                chain = MagicMock()
                chain.eq.return_value = chain
                chain.execute.return_value = MagicMock()
                return chain

            tbl.update.side_effect = capture_update

        elif table_name == "ecritures_sage":
            select_chain = MagicMock()
            select_chain.eq.return_value = select_chain
            resp = MagicMock()
            resp.data = []
            select_chain.execute.return_value = resp
            tbl.select.return_value = select_chain

        elif table_name == "journaux":
            insert_chain = MagicMock()
            insert_chain.execute.return_value = MagicMock()
            tbl.insert.return_value = insert_chain

        return tbl

    mock_sb.table.side_effect = table_side_effect

    agent = VerificateurAgent()

    with patch.object(agent, "_get_supabase", return_value=mock_sb):
        result = agent.run()

    # Au moins une anomalie compte_incoherent attendue
    assert any(a["type_anomalie"] == "compte_incoherent" for a in result["anomalies"])

    # Vérification : chaque payload d'UPDATE contient uniquement badge_anomalie (et anomalie_description)
    # et JAMAIS montant_ht, montant_ttc, compte_debit, compte_credit
    forbidden_keys = {"montant_ht", "montant_ttc", "compte_debit", "compte_credit"}
    for payload in update_calls:
        assert "badge_anomalie" in payload, (
            f"UPDATE attendu avec badge_anomalie, payload reçu : {payload}"
        )
        intersection = forbidden_keys & set(payload.keys())
        assert intersection == set(), (
            f"UPDATE interdit sur champ(s) comptable(s) : {intersection} — payload : {payload}"
        )
