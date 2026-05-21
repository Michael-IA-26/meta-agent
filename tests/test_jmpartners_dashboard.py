"""Tests pour apps.jmpartners.dashboard — JM Partners (démo beta 8 juin)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app() -> Any:
    """Import the app after patching heavy dependencies."""
    from apps.jmpartners.dashboard import app

    return app


@pytest.fixture()
def client() -> TestClient:
    """TestClient pour le dashboard FastAPI."""
    app = _make_app()
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1 — GET / renvoie du HTML avec les éléments clés
# ---------------------------------------------------------------------------


def test_root_returns_html(client: TestClient) -> None:
    """GET / doit renvoyer un HTML avec les sections kanban et calendrier."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    # Titre principal
    assert "JM Partners" in body
    # Sections kanban
    assert "Documents manquants" in body
    assert "En attente" in body
    assert "Complet" in body
    # Calendrier
    assert "Calendrier" in body
    # Bouton dry-run
    assert "dry-run" in body.lower() or "dry_run" in body.lower()


# ---------------------------------------------------------------------------
# Test 2 — GET /api/dossiers sans Supabase retourne les données mock
# ---------------------------------------------------------------------------


def test_get_dossiers_mock_fallback(client: TestClient) -> None:
    """Sans Supabase configuré, /api/dossiers retourne les dossiers mock."""
    with (
        patch("apps.jmpartners.dashboard.SUPABASE_URL", ""),
        patch("apps.jmpartners.dashboard.SUPABASE_SERVICE_KEY", ""),
    ):
        resp = client.get("/api/dossiers")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    # Vérifie la structure d'un dossier
    first = data[0]
    assert "id" in first
    assert "contact_nom" in first
    assert "type" in first
    assert "documents_manquants" in first
    assert "alertes" in first


# ---------------------------------------------------------------------------
# Test 3 — GET /api/echeances retourne TVA + IS bien structurés
# ---------------------------------------------------------------------------


def test_get_echeances_structure(client: TestClient) -> None:
    """GET /api/echeances doit retourner un objet avec les champs attendus."""
    resp = client.get("/api/echeances")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "rouge" in data
    assert "orange" in data
    assert "jaune" in data
    assert "echeances" in data
    assert isinstance(data["echeances"], list)
    assert isinstance(data["total"], int)


def test_get_echeances_types(client: TestClient) -> None:
    """Les échéances doivent être de type TVA ou IS."""
    resp = client.get("/api/echeances")
    data = resp.json()
    for e in data["echeances"]:
        assert e["type"] in ("TVA", "IS"), f"Type inattendu : {e['type']}"
        assert "deadline" in e
        assert "jours_restants" in e
        assert isinstance(e["jours_restants"], int)
        assert 0 <= e["jours_restants"] <= 30


# ---------------------------------------------------------------------------
# Test 4 — POST /api/relancer/{dossier_id} — mode mock (sans Supabase)
# ---------------------------------------------------------------------------


def test_relancer_dossier_mock(client: TestClient) -> None:
    """POST /api/relancer/{id} doit retourner un statut même en mode mock."""
    with (
        patch("apps.jmpartners.dashboard._supabase_available", return_value=False),
        patch(
            "apps.jmpartners.agents.document_checker.run",
            side_effect=RuntimeError("Supabase indisponible"),
        ),
    ):
        resp = client.post("/api/relancer/d001")
    assert resp.status_code == 200
    data = resp.json()
    assert "dossier_id" in data
    assert data["dossier_id"] == "d001"
    assert "statut" in data
    assert "message" in data


def test_relancer_dossier_with_mock_agents(client: TestClient) -> None:
    """POST /api/relancer/{id} doit appeler check_docs et send_relance si dispo."""
    mock_doc_result: dict[str, Any] = {
        "dossier_id": "d002",
        "contact_id": "c002",
        "type_dossier": "tva",
        "manquants": [
            {
                "nom_document": "CA Mensuel",
                "type_document": "ca_mensuel",
                "deadline": None,
                "urgence": None,
            }
        ],
        "complets": ["factures_tva"],
        "erreur": None,
    }
    mock_relance_result: dict[str, Any] = {
        "dossier_id": "d002",
        "contact_id": "c002",
        "statut": "envoye",
        "email_envoye": True,
        "message_id": "msg_001",
        "erreur": None,
    }
    with (
        patch(
            "apps.jmpartners.agents.document_checker.run", return_value=mock_doc_result
        ),
        patch(
            "apps.jmpartners.agents.relance_handler.run",
            return_value=mock_relance_result,
        ),
    ):
        resp = client.post("/api/relancer/d002")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dossier_id"] == "d002"


# ---------------------------------------------------------------------------
# Test 5 — POST /api/dry-run — orchestrateur mocké
# ---------------------------------------------------------------------------


def test_dry_run_with_mock_orchestrator(client: TestClient) -> None:
    """POST /api/dry-run doit retourner un résultat structuré via l'orchestrateur."""
    mock_result: dict = {
        "mail": {"emails": [], "statut": "ok"},
        "relances": [],
        "tva": {"declarations_analysees": 2, "alertes": 0, "statut": "ok"},
        "echeances": {"echeances_total": 3, "rouge": 0, "orange": 1, "vert": 2},
        "cloture": None,
        "acomptes_is": [],
        "erreurs": [],
    }
    with patch("apps.jmpartners.orchestrator.run", return_value=mock_result):
        resp = client.post("/api/dry-run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert "statut" in data
    assert "erreurs" in data


def test_dry_run_fallback_when_orchestrator_fails(client: TestClient) -> None:
    """POST /api/dry-run doit retourner un mock si l'orchestrateur lève une exception."""
    with patch(
        "apps.jmpartners.orchestrator.run",
        side_effect=RuntimeError("Orchestrateur indisponible"),
    ):
        resp = client.post("/api/dry-run")
    assert resp.status_code == 200
    data = resp.json()
    assert data["dry_run"] is True
    assert data["statut"] == "mock"
    assert "message" in data


# ---------------------------------------------------------------------------
# Test 6 — Calcul des échéances IS (dates connues)
# ---------------------------------------------------------------------------


def test_is_deadline_dates() -> None:
    """Les échéances IS tombent le 15 mars/juin/sep/dec."""
    from apps.jmpartners.dashboard import _next_is_deadlines

    deadlines = _next_is_deadlines()
    for e in deadlines:
        dl = date.fromisoformat(e["deadline"])
        assert dl.day == 15, f"Jour attendu 15, obtenu {dl.day}"
        assert dl.month in (3, 6, 9, 12), f"Mois IS invalide : {dl.month}"
        assert 0 <= e["jours_restants"] <= 30


# ---------------------------------------------------------------------------
# Test 7 — Calcul des échéances TVA (le 20 du mois suivant)
# ---------------------------------------------------------------------------


def test_tva_deadline_dates() -> None:
    """Les échéances TVA tombent le 20 du mois suivant."""
    from apps.jmpartners.dashboard import _next_tva_deadlines

    deadlines = _next_tva_deadlines()
    for e in deadlines:
        dl = date.fromisoformat(e["deadline"])
        assert dl.day == 20, f"Jour attendu 20, obtenu {dl.day}"
        assert 0 <= e["jours_restants"] <= 30
        assert e["type"] == "TVA"


# ---------------------------------------------------------------------------
# Test 8 — GET /api/dossiers avec Supabase mocké
# ---------------------------------------------------------------------------


def test_get_dossiers_from_supabase(client: TestClient) -> None:
    """Quand Supabase est disponible, les dossiers sont chargés depuis la DB."""
    mock_supabase_data = [
        {
            "id": "uuid-001",
            "contact_id": "c-001",
            "type": "bilan",
            "statut": "actif",
            "deadline": (date.today() + timedelta(days=10)).isoformat(),
            "contacts": {"nom": "Test Corp"},
        }
    ]

    mock_resp = MagicMock()
    mock_resp.data = mock_supabase_data

    mock_client = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_resp

    with (
        patch("apps.jmpartners.dashboard._supabase_available", return_value=True),
        patch("apps.jmpartners.dashboard._fetch_dossiers_from_supabase") as mock_fetch,
    ):
        mock_fetch.return_value = [
            {
                "id": "uuid-001",
                "contact_id": "c-001",
                "contact_nom": "Test Corp",
                "type": "bilan",
                "statut": "actif",
                "deadline": (date.today() + timedelta(days=10)).isoformat(),
                "documents_manquants": ["Grand Livre"],
                "documents_presents": ["Balance"],
                "alertes": ["J-15"],
            }
        ]
        resp = client.get("/api/dossiers")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["contact_nom"] == "Test Corp"
    assert "Grand Livre" in data[0]["documents_manquants"]


# ---------------------------------------------------------------------------
# Test 9 — GET /api/dossiers fallback Supabase down
# ---------------------------------------------------------------------------


def test_get_dossiers_supabase_down(client: TestClient) -> None:
    """GET /api/dossiers doit retourner les données mock si Supabase est down."""
    with (
        patch("apps.jmpartners.dashboard._supabase_available", return_value=True),
        patch(
            "apps.jmpartners.dashboard._fetch_dossiers_from_supabase",
            side_effect=Exception("Connection refused"),
        ),
    ):
        resp = client.get("/api/dossiers")

    assert resp.status_code == 200
    data = resp.json()
    # Doit retourner les données mock (au moins 1 dossier)
    assert isinstance(data, list)
    assert len(data) >= 1
    # Structure valide
    first = data[0]
    assert "id" in first
    assert "contact_nom" in first
    assert "documents_manquants" in first
    assert "alertes" in first


# ---------------------------------------------------------------------------
# Test 10 — GET /api/dossiers données réelles structurées
# ---------------------------------------------------------------------------


def test_get_dossiers_real_data(client: TestClient) -> None:
    """GET /api/dossiers avec données réelles retourne la structure attendue."""
    real_dossiers = [
        {
            "id": "d-real-001",
            "contact_id": "c-real-001",
            "contact_nom": "Gamma SAS",
            "type": "tva",
            "statut": "actif",
            "deadline": (date.today() + timedelta(days=5)).isoformat(),
            "documents_manquants": ["CA Mensuel"],
            "documents_presents": ["Factures TVA"],
            "alertes": ["J-7"],
        }
    ]

    with (
        patch("apps.jmpartners.dashboard._supabase_available", return_value=True),
        patch(
            "apps.jmpartners.dashboard._fetch_dossiers_from_supabase",
            return_value=real_dossiers,
        ),
    ):
        resp = client.get("/api/dossiers")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["contact_nom"] == "Gamma SAS"
    assert data[0]["type"] == "tva"
    assert "J-7" in data[0]["alertes"]
    assert "CA Mensuel" in data[0]["documents_manquants"]


# ---------------------------------------------------------------------------
# Test 11 — GET /api/echeances fallback Supabase down
# ---------------------------------------------------------------------------


def test_get_echeances_supabase_down(client: TestClient) -> None:
    """GET /api/echeances doit utiliser le calcul algorithmique si Supabase est down."""
    with patch(
        "apps.jmpartners.dashboard._get_supabase_client",
        side_effect=Exception("Supabase unreachable"),
    ):
        resp = client.get("/api/echeances")

    assert resp.status_code == 200
    data = resp.json()
    # Le fallback algorithmique doit fournir une réponse valide
    assert "total" in data
    assert "echeances" in data
    assert isinstance(data["echeances"], list)


# ---------------------------------------------------------------------------
# Test 12 — GET /api/echeances données réelles depuis Supabase
# ---------------------------------------------------------------------------


def test_get_echeances_real_data(client: TestClient) -> None:
    """GET /api/echeances avec Supabase mocké retourne les vraies données."""
    today = date.today()
    tva_row = {
        "id": "tva-001",
        "dossier_id": "d-001",
        "periode": "2026-04",
        "statut": "a_preparer",
        "deadline": (today + timedelta(days=8)).isoformat(),
        "montant_tva": 1500.0,
    }
    is_row = {
        "id": "is-001",
        "dossier_id": "d-002",
        "exercice": "2026",
        "statut": "a_payer",
        "deadline": (today + timedelta(days=4)).isoformat(),
        "montant": 3000.0,
    }

    mock_tva_resp = MagicMock()
    mock_tva_resp.data = [tva_row]
    mock_is_resp = MagicMock()
    mock_is_resp.data = [is_row]

    mock_client = MagicMock()
    # Premier appel → TVA, deuxième appel → IS
    mock_client.table.return_value.select.return_value.gte.return_value.lte.return_value.neq.return_value.execute.side_effect = [
        mock_tva_resp,
        mock_is_resp,
    ]

    with patch(
        "apps.jmpartners.dashboard._get_supabase_client",
        return_value=mock_client,
    ):
        resp = client.get("/api/echeances")

    assert resp.status_code == 200
    data = resp.json()
    assert "echeances" in data
    types_found = {e["type"] for e in data["echeances"]}
    # Au moins un des types doit être présent
    assert types_found & {"TVA", "IS"}
