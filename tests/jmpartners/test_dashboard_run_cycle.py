"""Tests POST /api/run-cycle — dashboard JM Partners."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.jmpartners.dashboard import create_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app())


def _orch_result() -> dict:
    return {
        "mail": {"traites": 0, "erreurs": []},
        "relances": [],
        "tva": {"declarations_analysees": 0},
        "echeances": {"echeances_total": 0},
        "cloture": None,
        "acomptes_is": [],
        "bilans": [],
        "declarations_is": [],
        "erreurs": [],
    }


def test_run_cycle_defaults_to_dry_run(client: TestClient) -> None:
    with patch("apps.jmpartners.orchestrator.run", return_value=_orch_result()) as mock_run:
        resp = client.post("/api/run-cycle", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    mock_run.assert_called_once_with(dry_run=True)


def test_run_cycle_real_requires_explicit_flag(client: TestClient) -> None:
    with patch("apps.jmpartners.orchestrator.run", return_value=_orch_result()) as mock_run:
        resp = client.post("/api/run-cycle", json={"dry_run": False})
    assert resp.status_code == 200
    mock_run.assert_called_once_with(dry_run=False)


def test_run_cycle_catches_exceptions(client: TestClient) -> None:
    with patch("apps.jmpartners.orchestrator.run", side_effect=RuntimeError("crash")):
        resp = client.post("/api/run-cycle", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["statut"] == "error"


def test_run_cycle_does_not_fire_irreversible_in_dry_run(client: TestClient) -> None:
    """dry_run=True is passed to orchestrator, which gates all irreversible steps."""
    with patch("apps.jmpartners.orchestrator.run", return_value=_orch_result()) as mock_run:
        client.post("/api/run-cycle", json={})
    mock_run.assert_called_with(dry_run=True)
