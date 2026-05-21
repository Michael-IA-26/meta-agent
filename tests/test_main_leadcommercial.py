import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from apscheduler.triggers.cron import CronTrigger

from apps.leadcommercial.main import _run_job, main, start_scheduler


def test_run_job_calls_orchestrator():
    with patch(
        "apps.leadcommercial.orchestrator.run", return_value=[{"siren": "123"}]
    ) as mock_run:
        _run_job()
    mock_run.assert_called_once_with()


def test_run_job_captures_sentry_on_error():
    with (
        patch(
            "apps.leadcommercial.orchestrator.run",
            side_effect=RuntimeError("boom"),
        ),
        patch("apps.leadcommercial.main.sentry_sdk.capture_exception") as mock_capture,
    ):
        _run_job()  # must not propagate the exception

    mock_capture.assert_called_once()
    captured = mock_capture.call_args.args[0]
    assert isinstance(captured, RuntimeError)


def test_start_scheduler_job_config():
    mock_scheduler = MagicMock()
    mock_scheduler.start.side_effect = KeyboardInterrupt

    with patch(
        "apps.leadcommercial.main.BlockingScheduler", return_value=mock_scheduler
    ):
        start_scheduler()

    mock_scheduler.add_job.assert_called_once()
    args, kwargs = mock_scheduler.add_job.call_args
    assert args[0] is _run_job
    assert isinstance(args[1], CronTrigger)
    assert kwargs["id"] == "leadcommercial_pipeline"
    assert kwargs["misfire_grace_time"] == 3600
    mock_scheduler.start.assert_called_once()


def test_main_once_flag_runs_job():
    with (
        patch("apps.leadcommercial.orchestrator.run", return_value=[]),
        patch("apps.leadcommercial.main.start_scheduler") as mock_start,
        patch("apps.leadcommercial.main.sentry_sdk.init"),
    ):
        main(argv=["--once"])

    mock_start.assert_not_called()


def test_main_no_once_starts_scheduler():
    with (
        patch("apps.leadcommercial.main.start_scheduler") as mock_start,
        patch("apps.leadcommercial.main.sentry_sdk.init"),
    ):
        main(argv=[])

    mock_start.assert_called_once()


if __name__ == "__main__":
    test_run_job_calls_orchestrator()
    test_run_job_captures_sentry_on_error()
    test_start_scheduler_job_config()
    test_main_once_flag_runs_job()
    test_main_no_once_starts_scheduler()
    print()
    print("5/5 tests passes !")
