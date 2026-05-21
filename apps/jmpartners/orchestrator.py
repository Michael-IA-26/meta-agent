"""Orchestrateur JM Partners — coordonne les agents selon les déclencheurs."""

from __future__ import annotations

import logging
from typing import TypedDict

from apps.jmpartners.agents.document_checker import DocumentCheckerResult
from apps.jmpartners.agents.document_checker import run as check_docs
from apps.jmpartners.agents.echeance_agent import EcheanceAgentResult
from apps.jmpartners.agents.echeance_agent import run as run_echeances
from apps.jmpartners.agents.mail_handler import MailHandlerResult
from apps.jmpartners.agents.mail_handler import run as handle_mail
from apps.jmpartners.agents.relance_handler import RelanceResult
from apps.jmpartners.agents.relance_handler import run as send_relance
from apps.jmpartners.agents.tva_agent import TvaAgentResult
from apps.jmpartners.agents.tva_agent import run as run_tva

__all__ = ["OrchestratorResult", "run"]

logger = logging.getLogger(__name__)


class OrchestratorResult(TypedDict):
    """Résultat d'un cycle complet de l'orchestrateur."""

    mail: MailHandlerResult | None
    relances: list[RelanceResult]
    tva: TvaAgentResult | None
    echeances: EcheanceAgentResult | None
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


def run(dry_run: bool = False) -> OrchestratorResult:
    """Exécute un cycle complet : emails → relances → TVA → échéances.

    Args:
        dry_run: Si True, simule le flux complet sans envoyer d'emails
                 ni écrire en base.

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

    logger.info("Orchestrateur JM Partners — cycle terminé")
    return OrchestratorResult(
        mail=mail_result,
        relances=relances,
        tva=tva_result,
        echeances=echeance_result,
        erreurs=erreurs,
    )
