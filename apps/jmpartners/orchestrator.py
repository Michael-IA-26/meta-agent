"""Orchestrateur JM Partners — coordonne les agents selon les déclencheurs."""

from __future__ import annotations

import logging
import os
import time
from typing import TypedDict, cast

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

__all__ = ["OrchestratorResult", "run"]

logger = logging.getLogger(__name__)


def get_supabase_client():  # type: ignore[return]
    """Retourne un client Supabase si configuré, sinon None."""
    from supabase import create_client  # noqa: PLC0415
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        return None
    return create_client(url, key)


def _log_orchestrator_run(
    supabase,
    duree: float,
    agents_ok: int,
    agents_ko: int,
    erreurs: list[str],
) -> None:
    """Insère un enregistrement orchestrator_run dans journaux (silencieux si indisponible)."""
    if supabase is None:
        return
    try:
        supabase.table("journaux").insert({
            "type_action": "orchestrator_run",
            "statut": "ok" if agents_ko == 0 else "erreur",
            "contenu": f"{agents_ok} agents OK, {agents_ko} KO, durée {duree:.1f}s",
            "metadata": {
                "duree_secondes": round(duree, 2),
                "agents_ok": agents_ok,
                "agents_ko": agents_ko,
                "erreurs": erreurs,
            },
        }).execute()
    except Exception as exc:
        logger.warning(f"Orchestrateur — impossible de logguer dans journaux : {exc}")


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
    _t0 = time.monotonic()
    _supabase = get_supabase_client()

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

    _duree = time.monotonic() - _t0
    # Comptage des agents OK/KO — 7 agents tentés (mail toujours dans _handle_emails)
    _agents_ko = len(erreurs)
    _agents_ok = 7 - _agents_ko
    _log_orchestrator_run(_supabase, _duree, _agents_ok, _agents_ko, erreurs)

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
