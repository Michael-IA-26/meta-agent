"""Tests for apps/leadcommercial/dashboard.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from apps.leadcommercial.dashboard import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_LEADS = [
    {
        "id": "uuid-1",
        "siren": "123456789",
        "denomination": "ACME SAS",
        "dept": "75",
        "commune": "Paris",
        "code_naf": "6920Z",
        "score": 85,
        "qualified": True,
        "created_at": "2026-05-21T10:00:00+00:00",
    },
    {
        "id": "uuid-2",
        "siren": "987654321",
        "denomination": "BETA SARL",
        "dept": "69",
        "commune": "Lyon",
        "code_naf": "7022Z",
        "score": 45,
        "qualified": False,
        "created_at": "2026-05-21T08:30:00+00:00",
    },
]

SAMPLE_STATS_ROWS = [
    {"score": 85, "qualified": True, "created_at": "2026-05-21T10:00:00+00:00"},
    {"score": 45, "qualified": False, "created_at": "2026-05-21T08:30:00+00:00"},
    {"score": 72, "qualified": True, "created_at": "2026-05-20T14:00:00+00:00"},
]


def _mock_supabase_client(
    leads_data: list, stats_rows: list | None = None
) -> MagicMock:
    """Build a mock Supabase client that returns the given data."""
    mock_client = MagicMock()

    # Each call to .table(...).select(...).order(...).limit(...).execute()
    # or .table(...).select(...).gte(...).execute() must chain properly.

    def make_chain(data: list) -> MagicMock:
        chain = MagicMock()
        chain.select.return_value = chain
        chain.order.return_value = chain
        chain.limit.return_value = chain
        chain.gte.return_value = chain
        execute_result = MagicMock()
        execute_result.data = data
        chain.execute.return_value = execute_result
        return chain

    leads_chain = make_chain(leads_data)
    today_chain = make_chain([{"id": "x"}] * len(leads_data))
    week_chain = make_chain(stats_rows if stats_rows is not None else SAMPLE_STATS_ROWS)

    # .table() is called multiple times; use side_effect to return different chains
    mock_client.table.side_effect = [leads_chain, week_chain, today_chain]
    return mock_client


# ---------------------------------------------------------------------------
# Test 1 — GET / returns HTML
# ---------------------------------------------------------------------------


def test_index_returns_html() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "LeadCommercial" in response.text
    assert "<table" in response.text
    assert "Lancer le pipeline" in response.text


# ---------------------------------------------------------------------------
# Test 2 — GET /api/leads returns JSON list
# ---------------------------------------------------------------------------


def test_get_leads_returns_list() -> None:
    mock_client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    execute_result = MagicMock()
    execute_result.data = SAMPLE_LEADS
    chain.execute.return_value = execute_result
    mock_client.table.return_value = chain

    with patch(
        "apps.leadcommercial.dashboard._get_supabase_client",
        return_value=mock_client,
    ):
        response = client.get("/api/leads")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["siren"] == "123456789"
    assert data[0]["denomination"] == "ACME SAS"


# ---------------------------------------------------------------------------
# Test 3 — GET /api/leads returns empty list when Supabase not configured
# ---------------------------------------------------------------------------


def test_get_leads_empty_when_supabase_not_configured() -> None:
    with patch(
        "apps.leadcommercial.dashboard._get_supabase_client",
        side_effect=ValueError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant"),
    ):
        response = client.get("/api/leads")

    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# Test 4 — GET /api/stats returns expected structure
# ---------------------------------------------------------------------------


def test_get_stats_structure() -> None:
    mock_client = MagicMock()

    week_chain = MagicMock()
    week_chain.select.return_value = week_chain
    week_chain.gte.return_value = week_chain
    week_result = MagicMock()
    week_result.data = SAMPLE_STATS_ROWS
    week_chain.execute.return_value = week_result

    today_chain = MagicMock()
    today_chain.select.return_value = today_chain
    today_chain.gte.return_value = today_chain
    today_result = MagicMock()
    today_result.data = [{"id": "x"}, {"id": "y"}]
    today_chain.execute.return_value = today_result

    mock_client.table.side_effect = [week_chain, today_chain]

    with patch(
        "apps.leadcommercial.dashboard._get_supabase_client",
        return_value=mock_client,
    ):
        response = client.get("/api/stats")

    assert response.status_code == 200
    stats = response.json()
    assert "leads_today" in stats
    assert "leads_week" in stats
    assert "qualified_week" in stats
    assert "qualification_rate" in stats
    assert "best_score" in stats
    assert stats["leads_week"] == 3
    assert stats["best_score"] == 85


# ---------------------------------------------------------------------------
# Test 5 — GET /api/stats fallback when Supabase missing
# ---------------------------------------------------------------------------


def test_get_stats_fallback_when_not_configured() -> None:
    with patch(
        "apps.leadcommercial.dashboard._get_supabase_client",
        side_effect=ValueError("SUPABASE_URL ou SUPABASE_SERVICE_KEY manquant"),
    ):
        response = client.get("/api/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["leads_today"] == 0
    assert stats["leads_week"] == 0
    assert stats["qualified_week"] == 0
    assert stats["qualification_rate"] == 0.0
    assert stats["best_score"] is None


# ---------------------------------------------------------------------------
# Test 6 — POST /api/run triggers pipeline and returns leads_found
# ---------------------------------------------------------------------------


def test_post_run_triggers_pipeline() -> None:
    fake_leads = [{"siren": "111111111"}, {"siren": "222222222"}]

    with patch(
        "apps.leadcommercial.pipeline.run_pipeline",
        return_value=fake_leads,
    ):
        response = client.post("/api/run")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["leads_found"] == 2


# ---------------------------------------------------------------------------
# Test 7 — POST /api/run returns 500 when pipeline raises
# ---------------------------------------------------------------------------


def test_post_run_returns_500_on_error() -> None:
    with patch(
        "apps.leadcommercial.pipeline.run_pipeline",
        side_effect=RuntimeError("Sirene API down"),
    ):
        response = client.post("/api/run")

    assert response.status_code == 500
    body = response.json()
    assert "detail" in body
