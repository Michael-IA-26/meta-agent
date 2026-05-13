import logging
import os

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.leadcommercial.pipeline import run_pipeline

logger = logging.getLogger(__name__)

SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() not in {
    "false",
    "0",
    "no",
}


def _run_job() -> None:
    """Execute the pipeline and forward any exception to Sentry."""
    try:
        leads = run_pipeline()
        logger.info(f"Job termine : {len(leads)} leads qualifies")
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error(f"Erreur pipeline : {exc}", exc_info=True)


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


def main() -> None:
    """Entry point: blocking scheduler or single run depending on SCHEDULER_ENABLED."""
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
    if SCHEDULER_ENABLED:
        start_scheduler()
    else:
        logger.info("SCHEDULER_ENABLED=false — execution immediate puis arret")
        _run_job()


if __name__ == "__main__":
    main()
