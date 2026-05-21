import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

import pytest

from apps.leadcommercial.supabase_client import (
    create_lock,
    fetch_icp,
    get_client,
    insert_lead,
    is_lead_locked,
    persist_lead,
)


def _mock_supabase() -> MagicMock:
    """Build a MagicMock that mimics the Supabase fluent query builder."""
    client = MagicMock()
    # select chain — empty result by default (no lock)
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # insert chain — returns a fake UUID
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "uuid-abc-123"}
    ]
    return client


def test_get_client_missing_credentials():
    with (
        patch("apps.leadcommercial.supabase_client._client", None),
        patch("apps.leadcommercial.supabase_client.SUPABASE_URL", ""),
        patch("apps.leadcommercial.supabase_client.SUPABASE_SERVICE_KEY", ""),
    ):
        with pytest.raises(ValueError, match="SUPABASE_URL"):
            get_client()


def test_is_lead_locked_true():
    client = _mock_supabase()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"siren": "123456789"}
    ]
    with patch("apps.leadcommercial.supabase_client.get_client", return_value=client):
        assert is_lead_locked("123456789") is True


def test_is_lead_locked_false():
    client = _mock_supabase()
    with patch("apps.leadcommercial.supabase_client.get_client", return_value=client):
        assert is_lead_locked("999999999") is False


def test_insert_lead_returns_uuid():
    client = _mock_supabase()
    lead = {
        "siren": "123456789",
        "denomination": "TEST SAS",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "commune": "PARIS",
        "dept": "75",
        "date_creation": "2026-05-09",
        "dirigeant_nom": "DUPONT",
        "dirigeant_prenom": "Jean",
        "dirigeant_email": "jean@example.com",
        "site_web": "https://example.com",
        "score": 100,
        "signal_type": "creation",
    }
    with (
        patch("apps.leadcommercial.supabase_client.get_client", return_value=client),
        patch("apps.leadcommercial.supabase_client.CABINET_ID", "cabinet-uuid"),
    ):
        result = insert_lead(lead)

    assert result == "uuid-abc-123"
    inserted_row = client.table.return_value.insert.call_args[0][0]
    assert inserted_row["siren"] == "123456789"
    assert inserted_row["cabinet_id"] == "cabinet-uuid"
    assert inserted_row["signal_source"] == "sirene"
    assert inserted_row["adresse"] == "PARIS"
    assert inserted_row["score"] == 100


def test_insert_lead_no_cabinet_id():
    with patch("apps.leadcommercial.supabase_client.CABINET_ID", ""):
        with pytest.raises(ValueError, match="CABINET_ID"):
            insert_lead({"siren": "123456789"})


def test_create_lock_inserts_row():
    client = _mock_supabase()
    with (
        patch("apps.leadcommercial.supabase_client.get_client", return_value=client),
        patch("apps.leadcommercial.supabase_client.CABINET_ID", "cabinet-uuid"),
    ):
        create_lock("123456789")

    locked_row = client.table.return_value.insert.call_args[0][0]
    assert locked_row["siren"] == "123456789"
    assert locked_row["cabinet_id"] == "cabinet-uuid"


def test_persist_lead_no_siren():
    result = persist_lead({"denomination": "SANS SIREN", "score": 90})
    assert result is False


def test_persist_lead_locked_skip():
    client = _mock_supabase()
    client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"siren": "123456789"}
    ]
    with patch("apps.leadcommercial.supabase_client.get_client", return_value=client):
        result = persist_lead(
            {"siren": "123456789", "score": 90, "signal_type": "creation"}
        )

    assert result is False
    client.table.return_value.insert.assert_not_called()


def test_persist_lead_unlocked_inserts():
    client = _mock_supabase()
    lead = {
        "siren": "987654321",
        "denomination": "RESTO SAS",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "commune": "BOULOGNE",
        "dept": "92",
        "date_creation": "2026-05-09",
        "score": 90,
        "signal_type": "creation",
        "dirigeant_nom": "",
        "dirigeant_prenom": "",
        "dirigeant_email": "",
        "site_web": "",
        "capital_social": None,
    }
    with (
        patch("apps.leadcommercial.supabase_client.get_client", return_value=client),
        patch("apps.leadcommercial.supabase_client.CABINET_ID", "cabinet-uuid"),
    ):
        result = persist_lead(lead)

    assert result is True
    # insert called twice: once for leads, once for lead_locks
    assert client.table.return_value.insert.call_count == 2


def _mock_supabase_with_icp(row: dict) -> MagicMock:
    """Build a mock Supabase client whose select chain returns a single ICP row."""
    client = _mock_supabase()
    (
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data
    ) = [row]
    return client


def test_fetch_icp_found():
    row = {
        "secteurs": ["56.10A", "56.10B"],
        "zone_deps": ["75", "92"],
        "forme_juridique": ["5710"],
        "signaux_prioritaires": ["creation"],
        "signaux_exclus": ["intention"],
        "scoring_rules": {"creation": 90},
    }
    client = _mock_supabase_with_icp(row)
    with patch("apps.leadcommercial.supabase_client.get_client", return_value=client):
        result = fetch_icp("cabinet-uuid")

    assert result is not None
    assert result["secteurs"] == ["56.10A", "56.10B"]
    assert result["signaux_exclus"] == ["intention"]
    assert result["scoring_rules"] == {"creation": 90}


def test_fetch_icp_not_found():
    client = _mock_supabase()
    (
        client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data
    ) = []
    with patch("apps.leadcommercial.supabase_client.get_client", return_value=client):
        result = fetch_icp("cabinet-uuid")
    assert result is None


def test_fetch_icp_db_error():
    with patch(
        "apps.leadcommercial.supabase_client.get_client",
        side_effect=RuntimeError("connexion refusee"),
    ):
        result = fetch_icp("cabinet-uuid")
    assert result is None


if __name__ == "__main__":
    test_get_client_missing_credentials()
    test_is_lead_locked_true()
    test_is_lead_locked_false()
    test_insert_lead_returns_uuid()
    test_insert_lead_no_cabinet_id()
    test_create_lock_inserts_row()
    test_persist_lead_no_siren()
    test_persist_lead_locked_skip()
    test_persist_lead_unlocked_inserts()
    test_fetch_icp_found()
    test_fetch_icp_not_found()
    test_fetch_icp_db_error()
    print()
    print("12/12 tests passes !")
