"""Entry point JM Partners — scheduler APScheduler ou exécution unique."""

from __future__ import annotations

import argparse
import calendar
import logging
import os
from datetime import datetime

import sentry_sdk
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from apps.jmpartners.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

_TZ = "Europe/Paris"


def _job_cycle_complet() -> None:
    """Cycle complet : mails, documents, échéances."""
    try:
        Orchestrator().run()
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("Erreur cycle complet : %s", exc, exc_info=True)


def _job_fin_de_mois() -> None:
    """Clôture mensuelle — déclenché le dernier jour du mois à 20h."""
    now = datetime.now()
    try:
        Orchestrator().on_fin_de_mois(now.year, now.month)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        logger.error("Erreur fin de mois : %s", exc, exc_info=True)


def _last_day_of_month() -> int:
    """Retourne le dernier jour du mois courant."""
    now = datetime.now()
    return calendar.monthrange(now.year, now.month)[1]


def start_scheduler() -> None:
    """Configure et démarre le scheduler APScheduler bloquant."""
    scheduler = BlockingScheduler(timezone=_TZ)

    # Cycle principal : toutes les 30 min en heures ouvrées
    scheduler.add_job(
        _job_cycle_complet,
        CronTrigger(
            day_of_week="mon-fri",
            hour="8-19",
            minute="*/30",
            timezone=_TZ,
        ),
        id="jmpartners_cycle_complet",
        name="Cycle complet JM Partners",
        misfire_grace_time=600,
        replace_existing=True,
    )

    # Clôture mensuelle : dernier jour du mois à 20h
    scheduler.add_job(
        _job_fin_de_mois,
        CronTrigger(day=_last_day_of_month(), hour=20, minute=0, timezone=_TZ),
        id="jmpartners_fin_de_mois",
        name="Clôture mensuelle JM Partners",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    # Surveillance des échéances : chaque matin à 8h
    scheduler.add_job(
        _job_cycle_complet,
        CronTrigger(hour=8, minute=0, timezone=_TZ),
        id="jmpartners_echeances_matin",
        name="Vérification échéances JM Partners",
        misfire_grace_time=3600,
        replace_existing=True,
    )

    logger.info(
        "Scheduler JM Partners démarré — cycle toutes les 30 min (lun-ven 8h-19h)"
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté proprement")


def main(argv: list[str] | None = None) -> None:
    """Entry point : scheduler bloquant ou exécution unique avec --once."""
    parser = argparse.ArgumentParser(description="JM Partners — assistant comptable")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exécute un cycle immédiatement puis quitte",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Cycle sans écriture Supabase ni notification",
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
        logger.info("--once : exécution immédiate puis arrêt")
        try:
            Orchestrator(dry_run=args.dry_run).run()
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            logger.error("Erreur --once : %s", exc, exc_info=True)
            raise
    else:
        start_scheduler()


if __name__ == "__main__":
    main()
