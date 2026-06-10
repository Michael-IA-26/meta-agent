"""Fixtures partagées pour la suite TDD jmpartners."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── Supabase ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_supabase():
    """Client Supabase entièrement mocké — aucun appel réseau."""
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table

    # Chaîne fluide par défaut : retourne une liste vide
    resp = MagicMock()
    resp.data = []
    resp.count = 0
    chain = table
    for attr in ("select", "insert", "update", "eq", "neq", "lte", "gte",
                 "in_", "limit", "single", "execute", "order"):
        m = MagicMock(return_value=chain)
        setattr(chain, attr, m)
    chain.execute.return_value = resp
    return client


@pytest.fixture()
def mock_supabase_env(monkeypatch):
    """Patch les variables d'env Supabase pour passer les gardes."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")


@pytest.fixture()
def mock_imap_env(monkeypatch):
    """Patch les variables IMAP pour passer la garde mail_handler."""
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("IMAP_USER", "test@example.com")
    monkeypatch.setenv("IMAP_PASSWORD", "secret")


@pytest.fixture()
def mock_anthropic_env(monkeypatch):
    """Patch la variable Anthropic pour passer la garde."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


# ── Données de test ───────────────────────────────────────────────────────────


@pytest.fixture()
def dossier_bilan():
    return {
        "id": "dos-bilan-1",
        "contact_id": "contact-1",
        "type": "bilan",
        "deadline": "2026-07-15",
        "statut": "en_cours",
        "contacts": {"nom": "SARL Dupont", "email": "contact@dupont.fr"},
    }


@pytest.fixture()
def dossier_tva():
    return {
        "id": "dos-tva-1",
        "contact_id": "contact-1",
        "type": "tva",
        "deadline": "2026-06-30",
        "statut": "en_cours",
    }


@pytest.fixture()
def declaration_tva_proche():
    """Déclaration TVA à J+7 — doit déclencher une alerte."""
    from datetime import date, timedelta
    deadline = (date.today() + timedelta(days=7)).isoformat()
    return {
        "id": "decl-1",
        "dossier_id": "dos-tva-1",
        "contact_id": "contact-1",
        "periode": "2026-05",
        "deadline": deadline,
        "statut": "a_preparer",
    }


@pytest.fixture()
def contact_sample():
    return {"id": "contact-1", "nom": "SARL Dupont", "email": "contact@dupont.fr"}
