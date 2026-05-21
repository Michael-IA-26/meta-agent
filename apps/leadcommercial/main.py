"""Entry point for the LeadCommercial pipeline."""
import argparse
import logging
import os

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.leadcommercial import orchestrator

logger = logging.getLogger(__name__)


def _run_job() -> None:
    """Execute the orchestrator and forward any exception to Sentry."""
    try:
        leads = orchestrator.run()
        logger.info("Job termine : %d leads qualifies", len(leads))
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("Erreur orchestrateur : %s", exc, exc_info=True)


def start_scheduler() -> None:
    """Configure and start the blocking APScheduler for the nightly pipeline."""
    scheduler = BlockingScheduler(timezone="Europe/Paris")
    scheduler.add_job(
        _run_job,
        CronTrigger(hour=2, minute=0, timezone="Europe/Paris"),
        id="leadcommercial_pipeline",
        name="Pipeline LeadCommercial",
        # Tolere jusqu'a 1h de retard si le container etait down a 02:00
        misfire_grace_time=3600,
    )
    logger.info(
        "Scheduler demarre — pipeline LeadCommercial chaque nuit a 02:00 Europe/Paris"
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrete proprement")


def main(argv: list[str] | None = None) -> None:
    """Entry point: blocking scheduler or single run with --once flag."""
    parser = argparse.ArgumentParser(description="LeadCommercial pipeline")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute le pipeline une fois immediatement puis quitte",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("DOPPLER_ENVIRONMENT", "dev"),
        traces_sample_rate=0.1,
    )

    if args.once:
        logger.info("--once : execution immediate puis arret")
        _run_job()
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
