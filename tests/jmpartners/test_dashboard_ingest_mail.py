"""Task 3 — Tests POST /api/ingest-mail."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    from apps.jmpartners.dashboard import create_app

    return TestClient(create_app())


_GRAPH_NOT_CONFIGURED_RESULT = {
    "traites": 0,
    "non_matches": 0,
    "emails": [],
    "erreurs": ["Graph non configuré"],
}

_OK_RESULT = {
    "traites": 2,
    "non_matches": 0,
    "emails": [],
    "erreurs": [],
}


# ---------------------------------------------------------------------------
# Test 1 — empty body defaults to dry_run=True
# ---------------------------------------------------------------------------


def test_ingest_mail_defaults_to_dry_run(client: TestClient) -> None:
    """POST /api/ingest-mail sans body appelle mail_handler.run avec dry_run=True."""
    with patch("apps.jmpartners.agents.mail_handler.run", return_value=_OK_RESULT) as mock_run:
        resp = client.post("/api/ingest-mail", json={})

    assert resp.status_code == 200
    mock_run.assert_called_once_with(dry_run=True)
    data = resp.json()
    assert data["dry_run"] is True
    assert data["traites"] == 2


# ---------------------------------------------------------------------------
# Test 2 — dry_run=false explicitly triggers real run
# ---------------------------------------------------------------------------


def test_ingest_mail_real_when_explicit(client: TestClient) -> None:
    """POST /api/ingest-mail avec dry_run=false appelle mail_handler.run(dry_run=False)."""
    with patch("apps.jmpartners.agents.mail_handler.run", return_value=_OK_RESULT) as mock_run:
        resp = client.post("/api/ingest-mail", json={"dry_run": False})

    assert resp.status_code == 200
    mock_run.assert_called_once_with(dry_run=False)
    data = resp.json()
    assert data["dry_run"] is False


# ---------------------------------------------------------------------------
# Test 3 — Graph not configured → 200 with erreurs (no 500)
# ---------------------------------------------------------------------------


def test_ingest_mail_graph_not_configured(client: TestClient) -> None:
    """Si Graph n'est pas configuré, l'endpoint retourne 200 avec erreurs (pas de 500)."""
    with patch(
        "apps.jmpartners.agents.mail_handler.run",
        return_value=_GRAPH_NOT_CONFIGURED_RESULT,
    ):
        resp = client.post("/api/ingest-mail", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert "erreurs" in data
    assert len(data["erreurs"]) > 0


# ---------------------------------------------------------------------------
# Test 4 — handler exception → 200 with error payload (no 500)
# ---------------------------------------------------------------------------


def test_ingest_mail_handler_exception_is_caught(client: TestClient) -> None:
    """Si mail_handler.run lève une exception, l'endpoint retourne 200 avec statut error."""
    with patch(
        "apps.jmpartners.agents.mail_handler.run",
        side_effect=RuntimeError("connexion IMAP perdue"),
    ):
        resp = client.post("/api/ingest-mail", json={})

    assert resp.status_code == 200
    data = resp.json()
    assert data["statut"] == "error"
    assert len(data["erreurs"]) > 0
