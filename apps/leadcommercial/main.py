"""Entry point for the LeadCommercial pipeline."""

import argparse
import logging
import os

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.leadcommercial import orchestrator
from apps.leadcommercial.config import load_config

logger = logging.getLogger(__name__)


def _run_job() -> None:
    """Execute the orchestrator (scheduler nightly run, config from YAML)."""
    try:
        cfg = load_config()
        leads = orchestrator.run(cfg=cfg)
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pas d'ecriture Supabase ni d'alerte Telegram (test local)",
    )
    parser.add_argument(
        "--code-postal",
        type=str,
        default=None,
        metavar="CP",
        help="Filtrer sur un seul code postal (surcharge le YAML)",
    )
    parser.add_argument(
        "--max-leads",
        type=int,
        default=None,
        metavar="N",
        help="Limite dure du nombre de leads traites (ex: 10)",
    )
    parser.add_argument(
        "--max-enrichments",
        type=int,
        default=None,
        metavar="N",
        help="Limite d'appels Dropcontact sur ce run (ex: 5)",
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Date de creation ciblee (un seul jour — surcharge le YAML)",
    )
    parser.add_argument(
        "--date-from",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Debut de fenetre de creation (surcharge le YAML)",
    )
    parser.add_argument(
        "--date-to",
        type=str,
        default=None,
        metavar="YYYY-MM-DD",
        help="Fin de fenetre de creation (surcharge le YAML)",
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

        # --date → fenêtre d'un seul jour (date_from = date_to = date)
        date_from_cli = args.date_from or args.date
        date_to_cli = args.date_to or args.date

        cfg = load_config(
            codes_postaux=[args.code_postal] if args.code_postal else None,
            date_creation_min=date_from_cli,
            date_creation_max=date_to_cli,
        )

        leads = orchestrator.run(
            cfg=cfg,
            dry_run=args.dry_run,
            max_leads=args.max_leads,
            max_enrichments=args.max_enrichments,
        )
        orchestrator.print_leads_report(leads)
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
