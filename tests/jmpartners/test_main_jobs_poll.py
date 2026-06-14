"""TDD — continuous jobs poll thread in main.py. Tests written first (red)."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

# ── _jobs_poll_seconds ────────────────────────────────────────────────────────

def test_jobs_poll_seconds_default(monkeypatch):
    monkeypatch.delenv("JOBS_POLL_SECONDS", raising=False)
    from apps.jmpartners.main import _jobs_poll_seconds
    assert _jobs_poll_seconds() == 60


def test_jobs_poll_seconds_from_env(monkeypatch):
    monkeypatch.setenv("JOBS_POLL_SECONDS", "30")
    from apps.jmpartners.main import _jobs_poll_seconds
    assert _jobs_poll_seconds() == 30


def test_jobs_poll_seconds_invalid_env_returns_default(monkeypatch):
    monkeypatch.setenv("JOBS_POLL_SECONDS", "not-a-number")
    from apps.jmpartners.main import _jobs_poll_seconds
    assert _jobs_poll_seconds() == 60


# ── run_jobs_poll ─────────────────────────────────────────────────────────────

def test_run_jobs_poll_calls_run_pending_jobs():
    """run_jobs_poll calls run_pending_jobs at least once before stop_event is set."""
    stop = threading.Event()
    call_count = {"n": 0}

    def fake_run_pending_jobs(handlers, supabase):
        call_count["n"] += 1
        stop.set()

    with (
        patch("apps.jmpartners.main.run_pending_jobs", side_effect=fake_run_pending_jobs),
        patch("apps.jmpartners.main.get_supabase_client", return_value=MagicMock()),
    ):
        from apps.jmpartners.main import run_jobs_poll
        run_jobs_poll(stop_event=stop, poll_seconds=0)

    assert call_count["n"] >= 1


def test_run_jobs_poll_stops_on_event():
    """run_jobs_poll exits promptly when stop_event is already set."""
    stop = threading.Event()
    stop.set()

    called = {"n": 0}

    def fake_run(_handlers, _supabase):
        called["n"] += 1

    with patch("apps.jmpartners.main.run_pending_jobs", side_effect=fake_run):
        from apps.jmpartners.main import run_jobs_poll
        run_jobs_poll(stop_event=stop, poll_seconds=0)

    assert called["n"] == 0


def test_run_jobs_poll_swallows_exceptions():
    """run_jobs_poll catches exceptions and continues (no crash)."""
    stop = threading.Event()
    call_count = {"n": 0}

    def noisy(*_a, **_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("DB down")
        stop.set()

    with (
        patch("apps.jmpartners.main.run_pending_jobs", side_effect=noisy),
        patch("apps.jmpartners.main.get_supabase_client", return_value=MagicMock()),
    ):
        from apps.jmpartners.main import run_jobs_poll
        run_jobs_poll(stop_event=stop, poll_seconds=0)

    assert call_count["n"] == 2


# ── run_jobs_poll is importable and has the right signature ────────────────────

def test_run_jobs_poll_is_exported():
    """run_jobs_poll must be importable from main."""
    from apps.jmpartners.main import run_jobs_poll
    assert callable(run_jobs_poll)
