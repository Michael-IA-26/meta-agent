"""Tests TDD — features prod (scheduler, IMAP poll, health, journalisation, Telegram)."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest


# ── Helpers réutilisés ────────────────────────────────────────────────────────

def _mail_result():
    return {"traites": 0, "non_matches": 0, "emails": [], "erreurs": []}


def _tva_result():
    return {"declarations_analysees": 0, "alertes_envoyees": 0,
            "pieces_manquantes_total": 0, "declarations": [], "erreurs": []}


def _echeance_result():
    return {"echeances_total": 0, "rouge": 0, "orange": 0, "vert": 0,
            "rapport_envoye": False, "echeances": [], "erreurs": []}


def _orchestrator_patches():
    return (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", return_value=_tva_result()),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    )


# ── Feature 1 : Scheduler configurable ───────────────────────────────────────

def test_scheduler_enabled_defaut_true(monkeypatch):
    monkeypatch.delenv("SCHEDULER_ENABLED", raising=False)
    from apps.jmpartners.main import _scheduler_enabled
    assert _scheduler_enabled() is True


def test_scheduler_desactive_via_env(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    from apps.jmpartners.main import _scheduler_enabled
    assert _scheduler_enabled() is False


def test_scheduler_desactive_insensible_casse(monkeypatch):
    monkeypatch.setenv("SCHEDULER_ENABLED", "FALSE")
    from apps.jmpartners.main import _scheduler_enabled
    assert _scheduler_enabled() is False


def test_cron_schedule_defaut(monkeypatch):
    monkeypatch.delenv("CRON_SCHEDULE", raising=False)
    from apps.jmpartners.main import _cron_schedule
    assert _cron_schedule() == "0 7 * * 1-5"


def test_cron_schedule_personnalise(monkeypatch):
    monkeypatch.setenv("CRON_SCHEDULE", "30 8 * * 1-5")
    from apps.jmpartners.main import _cron_schedule
    assert _cron_schedule() == "30 8 * * 1-5"


# ── Feature 2 : IMAP poll configurable ───────────────────────────────────────

def test_imap_poll_minutes_defaut(monkeypatch):
    monkeypatch.delenv("IMAP_POLL_MINUTES", raising=False)
    from apps.jmpartners.main import _imap_poll_minutes
    assert _imap_poll_minutes() == 15


def test_imap_poll_minutes_configurable(monkeypatch):
    monkeypatch.setenv("IMAP_POLL_MINUTES", "5")
    from apps.jmpartners.main import _imap_poll_minutes
    assert _imap_poll_minutes() == 5


def test_imap_poll_loop_appelle_mail_handler():
    """run_imap_poll appelle mail_handler.run() puis s'arrête sur stop_event."""
    stop = threading.Event()
    calls = []

    def fake_mail(**kw):
        calls.append(True)
        stop.set()
        return _mail_result()

    with patch("apps.jmpartners.main.handle_mail", side_effect=fake_mail):
        from apps.jmpartners.main import run_imap_poll
        run_imap_poll(stop_event=stop, poll_minutes=0)

    assert len(calls) >= 1


def test_imap_poll_respecte_stop_event():
    """run_imap_poll ne tourne pas si stop_event est déjà levé."""
    stop = threading.Event()
    stop.set()
    calls = []

    with patch("apps.jmpartners.main.handle_mail", side_effect=lambda **kw: calls.append(True)):
        from apps.jmpartners.main import run_imap_poll
        run_imap_poll(stop_event=stop, poll_minutes=0)

    assert calls == []


# ── Feature 3 : GET /health ───────────────────────────────────────────────────

def test_health_retourne_200():
    from fastapi.testclient import TestClient
    from apps.jmpartners.dashboard import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_structure_minimale():
    from fastapi.testclient import TestClient
    from apps.jmpartners.dashboard import app
    client = TestClient(app)
    data = client.get("/health").json()
    assert "statut" in data
    assert "agents" in data
    assert "dernier_run" in data


def test_health_statut_ok_sans_supabase(monkeypatch):
    """Sans Supabase, /health retourne statut=ok avec dernier_run=None."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    from fastapi.testclient import TestClient
    from apps.jmpartners.dashboard import app
    data = TestClient(app).get("/health").json()
    assert data["statut"] == "ok"
    assert data["dernier_run"] is None


def test_health_agents_liste_les_10_agents():
    from fastapi.testclient import TestClient
    from apps.jmpartners.dashboard import app
    data = TestClient(app).get("/health").json()
    agents = data["agents"]
    expected = {
        "mail_handler", "tva_agent", "echeance_agent", "cloture_handler",
        "acompte_is_agent", "bilan_agent", "declaration_is_agent",
        "document_checker", "relance_handler", "notification_agent",
    }
    assert expected == set(agents.keys())


def test_health_dernier_run_depuis_journaux(monkeypatch):
    """Si Supabase disponible, dernier_run est lu depuis journaux."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    sb = MagicMock()
    row = {
        "created_at": "2026-06-10T07:00:00Z",
        "metadata": {"duree_secondes": 42.0, "agents_ok": 7, "agents_ko": 0, "erreurs": []},
    }
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[row])
    for attr in ("select", "eq", "order", "limit"):
        setattr(chain, attr, MagicMock(return_value=chain))
    sb.table.return_value.select.return_value = chain

    with patch("apps.jmpartners.dashboard._get_supabase_client", return_value=sb):
        from fastapi.testclient import TestClient
        from apps.jmpartners.dashboard import app
        data = TestClient(app).get("/health").json()

    assert data["dernier_run"] is not None
    assert data["dernier_run"]["timestamp"] == "2026-06-10T07:00:00Z"
    assert data["dernier_run"]["agents_ok"] == 7


# ── Feature 4 : Orchestrateur → journaux ─────────────────────────────────────

def test_orchestrator_run_logue_dans_journaux(monkeypatch):
    """Chaque orchestrator.run() insère un enregistrement orchestrator_run."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    sb = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[{"id": "j-run-1"}])
    for attr in ("insert", "execute"):
        setattr(chain, attr, MagicMock(return_value=chain))
    sb.table.return_value.insert.return_value = chain

    patches = _orchestrator_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        with patch("apps.jmpartners.orchestrator._log_orchestrator_run") as mock_log:
            from apps.jmpartners.orchestrator import run as orchestrate
            orchestrate(dry_run=False)

    mock_log.assert_called_once()


def test_orchestrator_log_metadata_contient_cles_requises(monkeypatch):
    """_log_orchestrator_run reçoit les bonnes clés dans metadata."""
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "key")

    captured = {}

    def fake_log(supabase, duree, agents_ok, agents_ko, erreurs):
        captured["duree"] = duree
        captured["agents_ok"] = agents_ok
        captured["agents_ko"] = agents_ko
        captured["erreurs"] = erreurs

    patches = _orchestrator_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        with patch("apps.jmpartners.orchestrator._log_orchestrator_run", side_effect=fake_log):
            with patch("apps.jmpartners.orchestrator.get_supabase_client"):
                from apps.jmpartners.orchestrator import run as orchestrate
                orchestrate(dry_run=False)

    assert "duree" in captured
    assert isinstance(captured["duree"], float)
    assert isinstance(captured["agents_ok"], int)
    assert isinstance(captured["agents_ko"], int)
    assert isinstance(captured["erreurs"], list)


def test_orchestrator_log_absent_si_supabase_non_configure(monkeypatch):
    """Sans Supabase configuré, _log_orchestrator_run ne plante pas."""
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)

    patches = _orchestrator_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
        from apps.jmpartners.orchestrator import run as orchestrate
        result = orchestrate(dry_run=False)

    assert isinstance(result, dict)


# ── Feature 5 : Telegram sur crash agent ─────────────────────────────────────

def test_crash_agent_envoie_notification_telegram(monkeypatch):
    """Quand un agent lève une exception, _notify_agent_error est appelé."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "test-chat")

    patches = _orchestrator_patches()
    with patches[0], patches[3], patches[4], patches[5], patches[6]:
        with patch("apps.jmpartners.orchestrator.run_tva",
                   side_effect=Exception("TVA down")):
            with patch("apps.jmpartners.orchestrator.run_echeances",
                       return_value=_echeance_result()):
                with patch("apps.jmpartners.orchestrator._notify_agent_error") as mock_notify:
                    from apps.jmpartners.orchestrator import run as orchestrate
                    orchestrate(dry_run=False)

    mock_notify.assert_called_once()
    agent_name = mock_notify.call_args[0][0]
    assert "tva_agent" in agent_name


def test_crash_multiple_agents_multiple_notifications(monkeypatch):
    """Chaque agent qui crashe envoie sa propre notification."""
    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", side_effect=Exception("tva")),
        patch("apps.jmpartners.orchestrator.run_echeances", side_effect=Exception("ech")),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
        patch("apps.jmpartners.orchestrator._notify_agent_error") as mock_notify,
    ):
        from apps.jmpartners.orchestrator import run as orchestrate
        orchestrate(dry_run=False)

    assert mock_notify.call_count == 2


def test_telegram_non_configure_ne_plante_pas(monkeypatch):
    """Sans TELEGRAM_BOT_TOKEN, _notify_agent_error ne lève pas d'exception."""
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with (
        patch("apps.jmpartners.orchestrator.handle_mail", return_value=_mail_result()),
        patch("apps.jmpartners.orchestrator.run_tva", side_effect=Exception("TVA down")),
        patch("apps.jmpartners.orchestrator.run_echeances", return_value=_echeance_result()),
        patch("apps.jmpartners.orchestrator.ClotureHandler"),
        patch("apps.jmpartners.orchestrator.AcompteISAgent"),
        patch("apps.jmpartners.orchestrator.BilanAgent"),
        patch("apps.jmpartners.orchestrator.DeclarationISAgent"),
    ):
        from apps.jmpartners.orchestrator import run as orchestrate
        result = orchestrate(dry_run=False)

    assert isinstance(result, dict)
