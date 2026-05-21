"""Point d'entrée JM Partners — scheduler APScheduler ou exécution ponctuelle."""

from __future__ import annotations

import argparse
import logging
import sys

from apps.jmpartners.agents.document_checker import run as check_docs
from apps.jmpartners.agents.echeance_agent import run as run_echeances
from apps.jmpartners.agents.tva_agent import run as run_tva
from apps.jmpartners.orchestrator import OrchestratorResult
from apps.jmpartners.orchestrator import run as orchestrate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


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
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler non installé. Utilisez --once pour un run unique.")
        sys.exit(1)

    scheduler = BlockingScheduler(timezone="Europe/Paris")
    scheduler.add_job(
        orchestrate,
        CronTrigger(hour=8, minute=0, day_of_week="mon-fri"),
        kwargs={"dry_run": dry_run},
        id="cycle_matin",
        name="Cycle quotidien matin",
    )
    scheduler.add_job(
        run_echeances,
        CronTrigger(hour=17, minute=30, day_of_week="mon-fri"),
        kwargs={"dry_run": dry_run},
        id="rapport_echeances",
        name="Rapport échéances fin de journée",
    )

    logger.info("Scheduler JM Partners démarré (lun-ven 08h00 + 17h30)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler arrêté")


if __name__ == "__main__":
    main()
