"""Task 1 — Tests CORS pour l'app FastAPI (Lovable origin)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make(monkeypatch: pytest.MonkeyPatch, origins: str = "") -> TestClient:
    """Build a fresh app after setting the env var."""
    if origins:
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
    else:
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    # Import factory after env is set
    from apps.jmpartners.dashboard import create_app

    return TestClient(create_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# Test 1 — preflight allowed origin is echoed back
# ---------------------------------------------------------------------------


def test_cors_preflight_allows_configured_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPTIONS /api/dossiers avec une origin autorisée doit l'échanger en Access-Control-Allow-Origin."""
    client = _make(
        monkeypatch,
        "https://ai-books-buddy.lovable.app,https://preview.lovable.app",
    )
    resp = client.options(
        "/api/dossiers",
        headers={
            "Origin": "https://ai-books-buddy.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "https://ai-books-buddy.lovable.app"


# ---------------------------------------------------------------------------
# Test 2 — unknown origin is rejected (not reflected)
# ---------------------------------------------------------------------------


def test_cors_rejects_unknown_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    """OPTIONS avec une origin inconnue ne doit pas refléter l'origin dans la réponse."""
    client = _make(
        monkeypatch,
        "https://ai-books-buddy.lovable.app",
    )
    resp = client.options(
        "/api/dossiers",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin != "https://evil.example"


# ---------------------------------------------------------------------------
# Test 3 — env unset → no origins (locked down)
# ---------------------------------------------------------------------------


def test_cors_defaults_to_empty_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sans CORS_ALLOWED_ORIGINS, aucune origin n'est autorisée."""
    client = _make(monkeypatch, "")
    resp = client.options(
        "/api/dossiers",
        headers={
            "Origin": "https://ai-books-buddy.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin != "https://ai-books-buddy.lovable.app"


# ---------------------------------------------------------------------------
# Test 4 — allowed methods and credentials advertised
# ---------------------------------------------------------------------------


def test_cors_allows_credentials_and_common_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pour une origin autorisée, GET/POST/OPTIONS + allow-credentials sont annoncés."""
    client = _make(monkeypatch, "https://ai-books-buddy.lovable.app")
    resp = client.options(
        "/api/dossiers",
        headers={
            "Origin": "https://ai-books-buddy.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin == "https://ai-books-buddy.lovable.app"
    allow_credentials = resp.headers.get("access-control-allow-credentials", "")
    assert allow_credentials.lower() == "true"
    allow_methods = resp.headers.get("access-control-allow-methods", "")
    for method in ("GET", "POST"):
        assert method in allow_methods.upper(), f"{method} absent de allow-methods: {allow_methods}"
