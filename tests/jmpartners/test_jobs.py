"""Tests TDD — jobs queue (zero réseau)."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.jmpartners.jobs import claim_next_job, run_pending_jobs


def _sb_with_job(job=None):
    """Build a mock Supabase returning one pending job."""
    sb = MagicMock()
    rows = [job] if job else []
    (
        sb.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = rows
    sb.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value = None
    sb.table.return_value.update.return_value.eq.return_value.execute.return_value = None
    return sb


def _pending_job(job_id="job-1", job_type="export_sage", payload=None):
    return {"id": job_id, "type": job_type, "statut": "pending", "payload": payload or {}}


# ── claim_next_job ────────────────────────────────────────────────────────────

def test_claim_selects_oldest_pending_and_flips_to_running():
    """claim_next_job() selects oldest pending and updates statut to running."""
    job = _pending_job()
    sb = _sb_with_job(job)

    result = claim_next_job(supabase=sb)

    assert result is not None
    assert result["statut"] == "running"
    assert result["id"] == "job-1"
    # Verify the update was called with running + status guard
    update_call = sb.table.return_value.update.call_args
    assert update_call[0][0]["statut"] == "running"


def test_claim_empty_queue_returns_none():
    """Empty queue → returns None without side effects."""
    sb = _sb_with_job(None)

    result = claim_next_job(supabase=sb)

    assert result is None
    sb.table.return_value.update.assert_not_called()


# ── run_pending_jobs ──────────────────────────────────────────────────────────

def test_handler_success_marks_done():
    """Successful handler → job becomes 'done'."""
    job = _pending_job()
    sb = _sb_with_job(job)
    called_with = []

    def handler(j):
        called_with.append(j["id"])

    # After first call, return empty to stop loop
    (
        sb.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .limit.return_value
        .execute.return_value
        .data
    ) = [job]

    # Simpler: use side_effect on execute
    execute_mock = sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute
    execute_mock.side_effect = [
        MagicMock(data=[job]),
        MagicMock(data=[]),
    ]

    run_pending_jobs({"export_sage": handler}, supabase=sb)

    assert "job-1" in called_with
    # Verify 'done' was written
    update_calls = [str(c) for c in sb.table.return_value.update.call_args_list]
    assert any("done" in c for c in update_calls)


def test_handler_exception_marks_error():
    """Handler raises → job becomes 'error', error message stored."""
    job = _pending_job()
    sb = _sb_with_job(job)

    execute_mock = sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute
    execute_mock.side_effect = [
        MagicMock(data=[job]),
        MagicMock(data=[]),
    ]

    def bad_handler(j):
        raise ValueError("something broke")

    run_pending_jobs({"export_sage": bad_handler}, supabase=sb)

    update_calls = [str(c) for c in sb.table.return_value.update.call_args_list]
    assert any("error" in c for c in update_calls)
    assert any("something broke" in c for c in update_calls)


def test_unknown_job_type_marks_error_without_crash():
    """Unknown job type → 'error', poller loop continues."""
    job = _pending_job(job_type="unknown_type")
    sb = _sb_with_job(job)

    execute_mock = sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute
    execute_mock.side_effect = [
        MagicMock(data=[job]),
        MagicMock(data=[]),
    ]

    count = run_pending_jobs({}, supabase=sb)

    assert count == 1
    update_calls = [str(c) for c in sb.table.return_value.update.call_args_list]
    assert any("error" in c for c in update_calls)


def test_empty_queue_returns_zero_no_side_effects():
    """Empty queue → returns 0, no handler called, no updates."""
    sb = _sb_with_job(None)
    called = []

    count = run_pending_jobs({"export_sage": lambda j: called.append(j)}, supabase=sb)

    assert count == 0
    assert called == []
    sb.table.return_value.update.assert_not_called()
