"""Tests pour apps.jmpartners.agents.revision_agent."""
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from apps.jmpartners.agents.revision_agent import RevisionAgent

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_agent_with_data(
    ecritures_sage: list[dict] | None = None,
    ecritures: list[dict] | None = None,
) -> RevisionAgent:
    """Create RevisionAgent with mocked Supabase returning given data."""
    agent = RevisionAgent()
    mock_sb = MagicMock()

    sage_data = ecritures_sage or []
    ecr_data = ecritures or []

    def table_side_effect(name: str) -> MagicMock:  # type: ignore[return]
        t = MagicMock()
        if name == "ecritures_sage":
            t.select.return_value.execute.return_value.data = sage_data
        elif name == "ecritures":
            t.select.return_value.execute.return_value.data = ecr_data
        else:
            # revision, journaux inserts
            t.select.return_value.execute.return_value.data = []
            t.insert.return_value.execute.return_value.data = []
        t.insert.return_value.execute.return_value.data = []
        return t

    mock_sb.table.side_effect = table_side_effect
    agent._supabase = mock_sb  # type: ignore[assignment]
    return agent


# ─── Test 1 : doublon ─────────────────────────────────────────────────────────


def test_doublon_detecte_pas_de_correction_auto() -> None:
    """Same montant+tiers+date in both tables → anomalie 'doublon' created, corrigee=False."""
    ecritures_sage = [
        {
            "id": "sage-1",
            "compte": "401000",
            "tiers": "Fournisseur ABC",
            "date_ecriture": "20240101",
            "debit": 1500.00,
            "credit": 0.0,
            "libelle": "Facture",
            "source": "collaborateur",
        }
    ]
    ecritures = [
        {
            "id": "ecr-1",
            "tiers": "Fournisseur ABC",
            "date_ecriture": "20240101",
            "montant_ttc": 1500.00,
        }
    ]

    with patch("apps.jmpartners.agents.revision_agent.send_telegram_message"):
        agent = _make_agent_with_data(ecritures_sage=ecritures_sage, ecritures=ecritures)
        result = agent.run()

    doublons = [a for a in result["details"] if a["type"] == "doublon"]
    assert len(doublons) >= 1
    assert doublons[0]["corrigee"] is False
    assert doublons[0]["severite"] == "validation_requise"


# ─── Test 2 : compte incorrect ────────────────────────────────────────────────


def test_charge_sans_401_compte_incorrect() -> None:
    """6xxx debit without 401 for same tiers+date → 'compte_incorrect', severite='validation_requise'."""
    ecritures_sage = [
        {
            "id": "sage-2",
            "compte": "606000",
            "tiers": "Fournisseur XYZ",
            "date_ecriture": "20240115",
            "debit": 800.00,
            "credit": 0.0,
            "libelle": "Fournitures",
            "source": "collaborateur",
        }
        # No 401 entry for Fournisseur XYZ on 20240115
    ]

    with patch("apps.jmpartners.agents.revision_agent.send_telegram_message"):
        agent = _make_agent_with_data(ecritures_sage=ecritures_sage)
        result = agent.run()

    incorrects = [a for a in result["details"] if a["type"] == "compte_incorrect"]
    assert len(incorrects) >= 1
    assert incorrects[0]["severite"] == "validation_requise"
    assert incorrects[0]["corrigee"] is False


# ─── Test 3 : tiers imprécis ─────────────────────────────────────────────────


def test_tiers_imprecis_divers() -> None:
    """tiers='Fournisseur Divers' → 'tiers_imprecis'."""
    ecritures_sage = [
        {
            "id": "sage-3",
            "compte": "401000",
            "tiers": "Fournisseur Divers",
            "date_ecriture": "20240120",
            "debit": 200.00,
            "credit": 0.0,
            "libelle": "Divers achats",
            "source": "collaborateur",
        }
    ]

    with patch("apps.jmpartners.agents.revision_agent.send_telegram_message"):
        agent = _make_agent_with_data(ecritures_sage=ecritures_sage)
        result = agent.run()

    imprecis = [a for a in result["details"] if a["type"] == "tiers_imprecis"]
    assert len(imprecis) >= 1
    assert imprecis[0]["type"] == "tiers_imprecis"


# ─── Test 4 : validation_requise → corrigee=False TOUJOURS ───────────────────


def test_anomalie_validation_requise_corrigee_false() -> None:
    """RULE: for any validation_requise anomaly, corrigee=False always."""
    ecritures_sage = [
        {
            "id": "sage-4",
            "compte": "601000",
            "tiers": "INCONNU",
            "date_ecriture": "20240125",
            "debit": 999.00,
            "credit": 0.0,
            "libelle": "Charge sans 401",
            "source": "collaborateur",
        }
    ]

    with patch("apps.jmpartners.agents.revision_agent.send_telegram_message"):
        agent = _make_agent_with_data(ecritures_sage=ecritures_sage)
        result = agent.run()

    for anomalie in result["details"]:
        if anomalie["severite"] == "validation_requise":
            assert anomalie["corrigee"] is False, (
                f"Anomalie {anomalie['type']} avec severite=validation_requise "
                f"ne doit jamais être corrigée automatiquement"
            )


# ─── Test 5 : règle absolue — pas de correction de compte ────────────────────


def test_regle_absolue_pas_de_correction_compte() -> None:
    """Assert UPDATE on ecritures never includes compte_debit, compte_credit, montant_ht, montant_ttc keys."""
    FORBIDDEN_KEYS = {"compte_debit", "compte_credit", "montant_ht", "montant_ttc"}

    ecritures_sage = [
        {
            "id": "sage-5",
            "compte": "612000",
            "tiers": "Divers",
            "date_ecriture": "20240201",
            "debit": 350.00,
            "credit": 0.0,
            "libelle": "Loyer divers",
            "source": "collaborateur",
        }
    ]

    agent = RevisionAgent()
    mock_sb = MagicMock()

    all_insert_calls: list[dict] = []
    all_update_calls: list[dict] = []

    def table_side_effect(name: str) -> MagicMock:  # type: ignore[return]
        t = MagicMock()
        if name == "ecritures_sage":
            t.select.return_value.execute.return_value.data = ecritures_sage
        elif name == "ecritures":
            t.select.return_value.execute.return_value.data = []
        else:
            t.select.return_value.execute.return_value.data = []

        def capture_insert(payload):  # type: ignore[no-untyped-def]
            if isinstance(payload, dict):
                all_insert_calls.append(payload)
            elif isinstance(payload, list):
                all_insert_calls.extend(payload)
            m = MagicMock()
            m.execute.return_value.data = []
            return m

        def capture_update(payload):  # type: ignore[no-untyped-def]
            if isinstance(payload, dict):
                all_update_calls.append(payload)
            m = MagicMock()
            m.eq.return_value.execute.return_value.data = []
            return m

        t.insert.side_effect = capture_insert
        t.update.side_effect = capture_update
        return t

    mock_sb.table.side_effect = table_side_effect
    agent._supabase = mock_sb  # type: ignore[assignment]

    with patch("apps.jmpartners.agents.revision_agent.send_telegram_message"):
        agent.run()

    # Check no UPDATE contains forbidden keys
    for update_payload in all_update_calls:
        forbidden_found = FORBIDDEN_KEYS.intersection(update_payload.keys())
        assert not forbidden_found, (
            f"RÈGLE ABSOLUE VIOLÉE: UPDATE contient les clés interdites {forbidden_found}"
        )

    # Also check INSERT into ecritures (not ecritures_sage or revision) doesn't set montant
    for insert_payload in all_insert_calls:
        # Only flag if it looks like an ecritures update (has compte fields)
        for key in ("compte_debit", "compte_credit"):
            if key in insert_payload:
                # This would be a violation only if targeting "ecritures" directly
                # Since we can't distinguish table name here, we assert the field is absent
                # in any payload that also contains montant fields
                if any(k in insert_payload for k in ("montant_ht", "montant_ttc")):
                    pytest.fail(
                        f"RÈGLE ABSOLUE VIOLÉE: payload contient {key} et montant ensemble"
                    )


# ─── Test 6 : Telegram envoyé si anomalies en attente ────────────────────────


def test_telegram_envoye_si_anomalies_en_attente() -> None:
    """anomalies_en_attente > 0 → send_telegram_message called once."""
    ecritures_sage = [
        {
            "id": "sage-6",
            "compte": "607000",
            "tiers": "Fournisseur Inconnu",
            "date_ecriture": "20240210",
            "debit": 450.00,
            "credit": 0.0,
            "libelle": "Achat sans 401",
            "source": "collaborateur",
        }
    ]

    with patch(
        "apps.jmpartners.agents.revision_agent.send_telegram_message"
    ) as mock_telegram:
        agent = _make_agent_with_data(ecritures_sage=ecritures_sage)
        result = agent.run()

    assert result["anomalies_en_attente"] > 0
    mock_telegram.assert_called_once()
