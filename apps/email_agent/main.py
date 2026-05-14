"""Entry point — scheduler that triggers orchestrator.run() daily at 08:45."""
import argparse
import logging
import os
import sys
import time

import schedule
import sentry_sdk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from orchestrator import run  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("DOPPLER_ENVIRONMENT", "dev"),
    traces_sample_rate=0.1,
)


def run_daily_report() -> None:
    """Trigger the orchestrator pipeline and capture any unhandled exception in Sentry."""
    logger.info("Lancement du rapport quotidien...")
    try:
        run()
        logger.info("Rapport envoye avec succes.")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error("Erreur capturee par Sentry : %s", e)


def _build_parser() -> argparse.ArgumentParser:
    """Return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Agent email — rapport quotidien automatise."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Execute run_daily_report() une seule fois puis quitte.",
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()

    if args.once:
        run_daily_report()
        sys.exit(0)

    logger.info(
        "Agent email demarre — rapport envoye chaque jour a 08h45. Sentry : %s",
        bool(os.getenv("SENTRY_DSN")),
    )
    schedule.every().day.at("08:45").do(run_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)
