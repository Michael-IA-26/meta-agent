import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import MagicMock, patch

from apscheduler.triggers.cron import CronTrigger

from apps.leadcommercial.main import _run_job, main, start_scheduler


def test_run_job_calls_pipeline():
    with patch(
        "apps.leadcommercial.main.run_pipeline", return_value=[{"siren": "123"}]
    ) as mock_pipeline:
        _run_job()
    mock_pipeline.assert_called_once_with()


def test_run_job_captures_sentry_on_error():
    with (
        patch(
            "apps.leadcommercial.main.run_pipeline",
            side_effect=RuntimeError("boom"),
        ),
        patch(
            "apps.leadcommercial.main.sentry_sdk.capture_exception"
        ) as mock_capture,
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


def test_main_scheduler_enabled_calls_start_scheduler():
    with (
        patch("apps.leadcommercial.main.SCHEDULER_ENABLED", True),
        patch("apps.leadcommercial.main.start_scheduler") as mock_start,
        patch("apps.leadcommercial.main.sentry_sdk.init"),
    ):
        main()

    mock_start.assert_called_once()


def test_main_scheduler_disabled_runs_pipeline_once():
    with (
        patch("apps.leadcommercial.main.SCHEDULER_ENABLED", False),
        patch(
            "apps.leadcommercial.main.run_pipeline", return_value=[]
        ) as mock_pipeline,
        patch("apps.leadcommercial.main.start_scheduler") as mock_start,
        patch("apps.leadcommercial.main.sentry_sdk.init"),
    ):
        main()

    mock_pipeline.assert_called_once()
    mock_start.assert_not_called()


if __name__ == "__main__":
    test_run_job_calls_pipeline()
    test_run_job_captures_sentry_on_error()
    test_start_scheduler_job_config()
    test_main_scheduler_enabled_calls_start_scheduler()
    test_main_scheduler_disabled_runs_pipeline_once()
    print()
    print("5/5 tests passes !")
