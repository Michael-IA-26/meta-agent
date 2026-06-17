"""Task 2 — Tests GET /api/documents."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from tests.jmpartners.conftest import make_supabase_mock


@pytest.fixture
def client() -> TestClient:
    from apps.jmpartners.dashboard import create_app

    return TestClient(create_app())


# ---------------------------------------------------------------------------
# Test 1 — returns pipeline states grouped by statut
# ---------------------------------------------------------------------------


def test_documents_returns_pipeline_states(client: TestClient) -> None:
    """GET /api/documents retourne les documents avec leur statut pipeline."""
    rows = [
        {
            "id": "doc-001",
            "nom": "Grand Livre.pdf",
            "statut": "recu",
            "source": "outlook",
            "dossier_id": "dossier-001",
            "created_at": "2026-06-10T08:00:00Z",
        },
        {
            "id": "doc-002",
            "nom": "Balance.pdf",
            "statut": "analysé",
            "source": "outlook",
            "dossier_id": "dossier-001",
            "created_at": "2026-06-11T09:00:00Z",
        },
        {
            "id": "doc-003",
            "nom": "Factures.pdf",
            "statut": "presaisi",
            "source": "outlook",
            "dossier_id": "dossier-002",
            "created_at": "2026-06-12T10:00:00Z",
        },
    ]
    sb = make_supabase_mock(rows)
    with patch("apps.jmpartners.dashboard._get_supabase_client", return_value=sb):
        resp = client.get("/api/documents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert data["par_statut"]["recu"] == 1
    assert data["par_statut"]["analysé"] == 1
    assert data["par_statut"]["presaisi"] == 1
    assert len(data["documents"]) == 3


# ---------------------------------------------------------------------------
# Test 2 — filter by dossier_id passes .eq() to Supabase
# ---------------------------------------------------------------------------


def test_documents_filter_by_dossier(client: TestClient) -> None:
    """GET /api/documents?dossier_id=xxx filtre côté Supabase."""
    rows = [
        {
            "id": "doc-001",
            "nom": "GL.pdf",
            "statut": "recu",
            "source": "outlook",
            "dossier_id": "dossier-001",
            "created_at": "2026-06-10T08:00:00Z",
        }
    ]
    sb = make_supabase_mock(rows)
    with patch("apps.jmpartners.dashboard._get_supabase_client", return_value=sb):
        resp = client.get("/api/documents?dossier_id=dossier-001")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    # Verify that eq("dossier_id", ...) was called in the chain
    table_mock = sb.table.return_value
    eq_calls = [str(c) for c in table_mock.eq.call_args_list]
    assert any("dossier_id" in c for c in eq_calls)


# ---------------------------------------------------------------------------
# Test 3 — Supabase down → 200 with empty payload (no 500)
# ---------------------------------------------------------------------------


def test_documents_supabase_down_returns_empty_not_500(client: TestClient) -> None:
    """Si Supabase est indisponible, /api/documents retourne 200 vide plutôt qu'une 500."""
    with patch(
        "apps.jmpartners.dashboard._get_supabase_client",
        side_effect=Exception("Supabase unreachable"),
    ):
        resp = client.get("/api/documents")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["documents"] == []
    assert data["par_statut"] == {}
