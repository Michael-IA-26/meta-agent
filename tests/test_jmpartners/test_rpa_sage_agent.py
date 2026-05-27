"""Tests unitaires pour RPASageAgent."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent


def _make_supabase_mock(ecritures: list[dict] | None = None) -> MagicMock:
    sb = MagicMock()
    rows = ecritures if ecritures is not None else []
    ecr_resp = MagicMock()
    ecr_resp.data = rows
    (
        sb.table.return_value.select.return_value.eq.return_value.execute.return_value
    ) = ecr_resp
    sb.table.return_value.insert.return_value.execute.return_value = MagicMock()
    return sb


class TestRPASageAgent:
    def test_mode_stub_retourne_next_agent(self) -> None:
        sb = _make_supabase_mock([])
        agent = RPASageAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run(mode="stub")

        assert result["mode"] == "stub"
        assert result["next_agent"] == "miroir_sage_agent"

    def test_ecritures_lues_depuis_supabase(self) -> None:
        ecritures = [
            {"id": "e1", "statut": "a_saisir_sage"},
            {"id": "e2", "statut": "a_saisir_sage"},
            {"id": "e3", "statut": "a_saisir_sage"},
        ]
        sb = _make_supabase_mock(ecritures)
        agent = RPASageAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run(mode="stub")

        assert result["ecritures_a_saisir"] == 3
        assert result["ecritures_saisies"] == 0

    def test_log_journal_cree(self) -> None:
        sb = _make_supabase_mock([{"id": "e1"}])
        agent = RPASageAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            agent.run(mode="stub")

        # Verify that INSERT was called on journaux table
        insert_calls = [
            call
            for call in sb.table.call_args_list
            if call.args and call.args[0] == "journaux"
        ]
        assert len(insert_calls) >= 1

    def test_mode_non_implemente(self) -> None:
        sb = _make_supabase_mock()
        agent = RPASageAgent()
        with patch.object(agent, "_get_supabase", return_value=sb):
            result = agent.run(mode="fantome")

        assert result["mode"] == "fantome"
        assert result["next_agent"] == "miroir_sage_agent"
        assert result["ecritures_a_saisir"] == 0
        assert result["ecritures_saisies"] == 0
