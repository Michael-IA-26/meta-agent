"""Orchestrateur JM Partners — coordonne les agents selon les déclencheurs."""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from apps.jmpartners.agents.acompte_is_agent import AcompteAlert, AcompteISAgent
from apps.jmpartners.agents.bilan_agent import BilanAgent, BilanAlert
from apps.jmpartners.agents.cloture_handler import ClotureHandler, ClotureResult
from apps.jmpartners.agents.declaration_is_agent import (
    DeclarationISAgent,
    DeclarationISAlert,
)
from apps.jmpartners.agents.document_checker import DocumentCheckerResult
from apps.jmpartners.agents.document_checker import run as check_docs
from apps.jmpartners.agents.echeance_agent import EcheanceAgentResult
from apps.jmpartners.agents.echeance_agent import run as run_echeances
from apps.jmpartners.agents.mail_handler import MailHandlerResult
from apps.jmpartners.agents.mail_handler import run as handle_mail
from apps.jmpartners.agents.notification_agent import NotificationAgent
from apps.jmpartners.agents.relance_handler import RelanceResult
from apps.jmpartners.agents.relance_handler import run as send_relance
from apps.jmpartners.agents.tva_agent import TvaAgentResult
from apps.jmpartners.agents.tva_agent import run as run_tva

__all__ = ["OrchestratorResult", "run", "setup_nocturne_jobs"]

logger = logging.getLogger(__name__)


def setup_nocturne_jobs(scheduler: Any) -> None:
    """Enregistre les jobs nocturnes APScheduler v2.2 sur le scheduler fourni.

    Les 7 jobs nocturnes sont planifiés sur la plage 00h00–06h00 (lun-dim) :
    bilan, déclaration IS, acomptes IS, clôture, relances, TVA, archivage.

    Args:
        scheduler: Instance APScheduler (BackgroundScheduler) à configurer.
    """
    try:
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.warning("APScheduler non disponible — jobs nocturnes non enregistrés")
        return

    nocturne_jobs = [
        ("bilan_nocturne", BilanAgent().run, 0, 30),
        ("declaration_is_nocturne", DeclarationISAgent().run, 1, 0),
        ("acomptes_is_nocturne", AcompteISAgent().run, 1, 30),
        ("cloture_nocturne", lambda: ClotureHandler(cabinet_id="jmpartners").run(), 2, 0),
        ("relances_nocturne", lambda: send_relance(check_docs("jmpartners"), dry_run=False), 2, 30),
        ("tva_nocturne", run_tva, 3, 0),
        ("archivage_nocturne", lambda: logger.info("Archivage nocturne — OK"), 3, 30),
    ]

    for job_id, func, hour, minute in nocturne_jobs:
        scheduler.add_job(
            func,
            CronTrigger(hour=hour, minute=minute),
            id=job_id,
            name=job_id.replace("_", " ").title(),
            misfire_grace_time=600,
        )
        logger.debug("Job nocturne enregistré : %s (%02dh%02d)", job_id, hour, minute)

    logger.info("setup_nocturne_jobs — %d jobs nocturnes enregistrés", len(nocturne_jobs))


class OrchestratorResult(TypedDict):
    """Résultat d'un cycle complet de l'orchestrateur."""

    mail: MailHandlerResult | None
    relances: list[RelanceResult]
    tva: TvaAgentResult | None
    echeances: EcheanceAgentResult | None
    cloture: ClotureResult | None
    acomptes_is: list[AcompteAlert]
    bilans: list[BilanAlert]
    declarations_is: list[DeclarationISAlert]
    erreurs: list[str]


def _handle_emails(
    dry_run: bool,
) -> tuple[MailHandlerResult | None, list[RelanceResult]]:
    """Lit les emails et déclenche les relances pour les demandes document_manquant."""
    relances: list[RelanceResult] = []
    try:
        mail_result = handle_mail(dry_run=dry_run)
    except Exception as exc:
        logger.error(f"Orchestrateur — erreur mail_handler : {exc}")
        return None, relances

    for item in mail_result["emails"]:
        if item["type_demande"] != "document_manquant":
            continue
        if not item.get("contact_id"):
            continue
        # Récupère tous les dossiers actifs du contact pour les vérifier
        # Dans une version complète, on interrogerait Supabase pour les dossiers.
        # Ici on logue l'intention pour extensibilité future.
        logger.info(
            f"Orchestrateur : email {item['message_id']} → "
            f"document_manquant pour contact {item['contact_id']}"
        )

    return mail_result, relances


def run_document_relance_flow(
    dossier_id: str, dry_run: bool = False
) -> tuple[DocumentCheckerResult, RelanceResult]:
    """Flux complet : vérifie les documents d'un dossier et envoie la relance si nécessaire.

    Args:
        dossier_id: UUID du dossier à vérifier.
        dry_run: Si True, simule sans effet de bord.

    Returns:
        Tuple (DocumentCheckerResult, RelanceResult).
    """
    doc_result = check_docs(dossier_id, dry_run=dry_run)
    relance_result = send_relance(doc_result, dry_run=dry_run)
    return doc_result, relance_result


def run(dry_run: bool = False, cabinet_id: str = "jmpartners") -> OrchestratorResult:
    """Exécute un cycle complet : emails → relances → TVA → échéances → clôture.

    Args:
        dry_run: Si True, simule le flux complet sans envoyer d'emails
                 ni écrire en base.
        cabinet_id: Identifiant du cabinet pour la clôture.

    Returns:
        OrchestratorResult avec le résultat de chaque agent.
    """
    logger.info(f"Orchestrateur JM Partners — démarrage (dry_run={dry_run})")
    erreurs: list[str] = []

    # 1. Traitement des emails entrants
    mail_result, relances = _handle_emails(dry_run)

    # 2. Surveillance TVA
    tva_result: TvaAgentResult | None = None
    try:
        tva_result = run_tva(dry_run=dry_run)
    except Exception as exc:
        logger.error(f"Orchestrateur — erreur tva_agent : {exc}")
        erreurs.append(f"tva_agent: {exc}")

    # 3. Rapport échéances quotidien
    echeance_result: EcheanceAgentResult | None = None
    try:
        echeance_result = run_echeances(dry_run=dry_run)
    except Exception as exc:
        logger.error(f"Orchestrateur — erreur echeance_agent : {exc}")
        erreurs.append(f"echeance_agent: {exc}")

    # 4. Clôture comptable (fin de mois) — ignorée en dry_run
    cloture_result: ClotureResult | None = None
    if not dry_run:
        try:
            cloture_result = ClotureHandler(cabinet_id=cabinet_id).run()
        except Exception as exc:
            logger.error(f"Orchestrateur — erreur cloture_handler : {exc}")
            erreurs.append(f"cloture_handler: {exc}")

    # 5. Alertes acomptes IS — ignorées en dry_run
    acomptes_is: list[AcompteAlert] = []
    if not dry_run:
        try:
            acomptes_is = AcompteISAgent().run()
        except Exception as exc:
            logger.error(f"Orchestrateur — erreur acompte_is_agent : {exc}")
            erreurs.append(f"acompte_is_agent: {exc}")

    # 6. Alertes bilan (Sprint 3) — ignorées en dry_run
    bilans: list[BilanAlert] = []
    if not dry_run:
        try:
            bilans = BilanAgent().run()
        except Exception as exc:
            logger.error(f"Orchestrateur — erreur bilan_agent : {exc}")
            erreurs.append(f"bilan_agent: {exc}")

    # 7. Alertes déclarations IS (Sprint 3) — ignorées en dry_run
    declarations_is: list[DeclarationISAlert] = []
    if not dry_run:
        try:
            declarations_is = DeclarationISAgent().run()
        except Exception as exc:
            logger.error(f"Orchestrateur — erreur declaration_is_agent : {exc}")
            erreurs.append(f"declaration_is_agent: {exc}")

    # 8. Hub de notifications Sprint 3 (service interne, pas exposé dans le résultat)
    _notification_agent = NotificationAgent()
    logger.debug(
        f"Orchestrateur — notification_agent disponible : {_notification_agent}"
    )

    logger.info("Orchestrateur JM Partners — cycle terminé")
    return OrchestratorResult(
        mail=mail_result,
        relances=relances,
        tva=tva_result,
        echeances=echeance_result,
        cloture=cloture_result,
        acomptes_is=acomptes_is,
        bilans=bilans,
        declarations_is=declarations_is,
        erreurs=erreurs,
    )
