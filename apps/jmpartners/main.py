"""Point d'entrée JM Partners — scheduler APScheduler ou exécution ponctuelle."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

from apps.jmpartners.agents.document_checker import run as check_docs
from apps.jmpartners.agents.echeance_agent import run as run_echeances
from apps.jmpartners.agents.mail_handler import run as handle_mail
from apps.jmpartners.agents.tva_agent import run as run_tva
from apps.jmpartners.jobs import run_pending_jobs
from apps.jmpartners.orchestrator import OrchestratorResult, get_supabase_client
from apps.jmpartners.orchestrator import run as orchestrate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _scheduler_enabled() -> bool:
    """Retourne True si le scheduler cron doit démarrer (SCHEDULER_ENABLED != 'false')."""
    return os.getenv("SCHEDULER_ENABLED", "true").strip().lower() != "false"


def _cron_schedule() -> str:
    """Retourne l'expression cron du cycle principal (défaut : 07h00 lun-ven)."""
    return os.getenv("CRON_SCHEDULE", "0 7 * * 1-5")


def _imap_poll_minutes() -> int:
    """Retourne l'intervalle de polling IMAP en minutes (défaut : 15)."""
    try:
        return int(os.getenv("IMAP_POLL_MINUTES", "15"))
    except ValueError:
        return 15


def _jobs_poll_seconds() -> int:
    """Retourne l'intervalle de polling des jobs en secondes (défaut : 60)."""
    try:
        return int(os.getenv("JOBS_POLL_SECONDS", "60"))
    except ValueError:
        return 60


def run_imap_poll(
    stop_event: threading.Event | None = None,
    poll_minutes: int | None = None,
) -> None:
    """Boucle infinie qui appelle mail_handler.run() toutes les N minutes.

    Args:
        stop_event: si levé, la boucle s'arrête avant le prochain appel.
        poll_minutes: intervalle en minutes (None = lit IMAP_POLL_MINUTES).
    """
    if stop_event is not None and stop_event.is_set():
        return
    interval = poll_minutes if poll_minutes is not None else _imap_poll_minutes()
    logger.info(f"IMAP poll démarré (intervalle : {interval} min)")
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            result = handle_mail(dry_run=False)
            logger.info(
                f"IMAP poll : {result['traites']} traités, "
                f"{result['non_matches']} non matchés"
            )
        except Exception as exc:
            logger.error(f"IMAP poll — erreur mail_handler : {exc}")
        if stop_event is not None:
            stop_event.wait(interval * 60)
            if stop_event.is_set():
                break
        else:
            time.sleep(interval * 60)


def run_jobs_poll(
    stop_event: threading.Event | None = None,
    poll_seconds: int | None = None,
) -> None:
    """Boucle infinie qui traite la file de jobs Supabase toutes les N secondes.

    Args:
        stop_event: si levé, la boucle s'arrête avant le prochain appel.
        poll_seconds: intervalle en secondes (None = lit JOBS_POLL_SECONDS).
    """
    if stop_event is not None and stop_event.is_set():
        return
    interval = poll_seconds if poll_seconds is not None else _jobs_poll_seconds()
    logger.info(f"Jobs poll démarré (intervalle : {interval} s)")
    supabase = get_supabase_client()
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        try:
            run_pending_jobs({}, supabase=supabase)
        except Exception as exc:
            logger.error(f"Jobs poll — erreur : {exc}")
        if stop_event is not None:
            stop_event.wait(interval)
            if stop_event.is_set():
                break
        else:
            time.sleep(interval)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JM Partners — agent comptable")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exécute un cycle unique puis quitte",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule le flux complet sans effet de bord",
    )
    parser.add_argument(
        "--check-dossier",
        metavar="DOSSIER_ID",
        help="Vérifie les documents d'un dossier spécifique",
    )
    parser.add_argument(
        "--echeances",
        action="store_true",
        help="Génère uniquement le rapport des échéances",
    )
    parser.add_argument(
        "--tva",
        action="store_true",
        help="Vérifie uniquement les échéances TVA",
    )
    return parser.parse_args()


def main() -> None:
    """Exécute le cycle ou lance le scheduler selon les arguments."""
    args = _parse_args()
    dry_run = args.dry_run

    if dry_run:
        logger.info("Mode DRY RUN activé — aucun email ni écriture Supabase")

    if args.check_dossier:
        result = check_docs(args.check_dossier, dry_run=dry_run)
        logger.info(
            f"Dossier {args.check_dossier} : "
            f"{len(result['manquants'])} manquant(s), "
            f"{len(result['complets'])} complet(s)"
        )
        if result["erreur"]:
            logger.error(result["erreur"])
            sys.exit(1)
        return

    if args.echeances:
        run_echeances(dry_run=dry_run)
        return

    if args.tva:
        run_tva(dry_run=dry_run)
        return

    if args.once:
        orch_result: OrchestratorResult = orchestrate(dry_run=dry_run)
        logger.info(
            f"Cycle terminé — "
            f"{orch_result['tva']['declarations_analysees'] if orch_result['tva'] else 0} TVA, "
            f"{orch_result['echeances']['echeances_total'] if orch_result['echeances'] else 0} échéances, "
            f"{len(orch_result['acomptes_is'])} alertes IS, "
            f"clôture={orch_result['cloture']['statut'] if orch_result['cloture'] else 'skip'}"
        )
        return

    # Mode scheduler
    if not _scheduler_enabled():
        logger.info("Scheduler désactivé (SCHEDULER_ENABLED=false) — arrêt.")
        return

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler non installé. Utilisez --once pour un run unique.")
        sys.exit(1)

    cron = _cron_schedule()
    scheduler = BlockingScheduler(timezone="Europe/Paris")
    scheduler.add_job(
        orchestrate,
        CronTrigger.from_crontab(cron, timezone="Europe/Paris"),
        kwargs={"dry_run": dry_run},
        id="cycle_principal",
        name=f"Cycle principal ({cron})",
    )
    scheduler.add_job(
        run_echeances,
        CronTrigger(hour=17, minute=30, day_of_week="mon-fri"),
        kwargs={"dry_run": dry_run},
        id="rapport_echeances",
        name="Rapport échéances fin de journée",
    )

    # Shared stop event for background threads
    stop_event = threading.Event()

    # Démarrage du polling IMAP en arrière-plan si configuré
    imap_host = os.getenv("IMAP_HOST", "")
    if imap_host:
        imap_thread = threading.Thread(
            target=run_imap_poll,
            kwargs={"stop_event": stop_event},
            daemon=True,
            name="imap-poll",
        )
        imap_thread.start()
        logger.info(f"IMAP poll démarré en arrière-plan ({_imap_poll_minutes()} min)")

    # Démarrage du polling des jobs en arrière-plan
    jobs_thread = threading.Thread(
        target=run_jobs_poll,
        kwargs={"stop_event": stop_event},
        daemon=True,
        name="jobs-poll",
    )
    jobs_thread.start()
    logger.info(f"Jobs poll démarré en arrière-plan ({_jobs_poll_seconds()} s)")

    logger.info(f"Scheduler JM Partners démarré — cron principal : {cron}")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        stop_event.set()
        logger.info("Scheduler arrêté")


if __name__ == "__main__":
    main()
