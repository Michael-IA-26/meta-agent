"""Task 6 — Test que le mail poll démarre quand Graph est configuré."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _run_main_with_scheduler(mock_blocking: MagicMock) -> MagicMock:
    """Reload main and call main() with a clean sys.argv (scheduler mode = no --once flag)."""
    import importlib
    import sys

    with patch.dict(
        "sys.modules",
        {
            "apscheduler": MagicMock(),
            "apscheduler.schedulers": MagicMock(),
            "apscheduler.schedulers.blocking": MagicMock(BlockingScheduler=mock_blocking),
            "apscheduler.triggers": MagicMock(),
            "apscheduler.triggers.cron": MagicMock(),
        },
    ), patch.object(sys, "argv", ["main"]):
        import apps.jmpartners.main as main_mod

        importlib.reload(main_mod)
        try:
            main_mod.main()
        except SystemExit:
            pass
    return mock_blocking.return_value


def test_mail_poll_starts_when_graph_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le scheduler ajoute le job orchestrate complet quand GRAPH_TENANT_ID est présent."""
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant-test-id")

    mock_blocking = MagicMock()
    mock_instance = MagicMock()
    mock_instance.start.side_effect = SystemExit(0)
    mock_blocking.return_value = mock_instance

    instance = _run_main_with_scheduler(mock_blocking)
    job_ids = [c.kwargs.get("id", "") for c in instance.add_job.call_args_list]
    assert "cycle_matin" in job_ids, "cycle_matin doit être planifié quand Graph est configuré"


def test_mail_poll_disabled_when_graph_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sans GRAPH_TENANT_ID, cycle_matin n'est pas planifié (fallback écheances seulement)."""
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)

    mock_blocking = MagicMock()
    mock_instance = MagicMock()
    mock_instance.start.side_effect = SystemExit(0)
    mock_blocking.return_value = mock_instance

    instance = _run_main_with_scheduler(mock_blocking)
    job_ids = [c.kwargs.get("id", "") for c in instance.add_job.call_args_list]
    assert "cycle_matin" not in job_ids, "cycle_matin ne doit pas être planifié sans Graph"
