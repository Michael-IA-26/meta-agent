"""Orchestrateur JM Partners v2.2 — 13 agents, cycle diurne + nocturne."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TypedDict

from apscheduler.schedulers.background import BackgroundScheduler

from apps.jmpartners.agents.acompte_is_agent import AcompteAlert, AcompteISAgent
from apps.jmpartners.agents.bilan_agent import BilanAgent, BilanAlert
from apps.jmpartners.agents.cloture_handler import ClotureHandler, ClotureResult
from apps.jmpartners.agents.collecte_agent import CollecteAgent, CollecteResult
from apps.jmpartners.agents.declaration_is_agent import (
    DeclarationISAgent,
    DeclarationISAlert,
)
from apps.jmpartners.agents.document_checker import DocumentCheckerResult
from apps.jmpartners.agents.document_checker import run as check_docs
from apps.jmpartners.agents.echeance_agent import EcheanceAgentResult
from apps.jmpartners.agents.echeance_agent import run as run_echeances
from apps.jmpartners.agents.ged_agent import GEDAgent, GEDResult
from apps.jmpartners.agents.mail_handler import MailHandlerResult
from apps.jmpartners.agents.mail_handler import run as handle_mail
from apps.jmpartners.agents.miroir_sage_agent import MiroirSageAgent
from apps.jmpartners.agents.notification_agent import NotificationAgent
from apps.jmpartners.agents.ocr_agent import OCRAgent, OCRAgentResult
from apps.jmpartners.agents.presaisie_agent import PresaisieAgent, PresaisieResult
from apps.jmpartners.agents.relance_handler import RelanceResult
from apps.jmpartners.agents.relance_handler import run as send_relance
from apps.jmpartners.agents.revision_agent import RevisionAgent
from apps.jmpartners.agents.rpa_sage_agent import RPASageAgent
from apps.jmpartners.agents.tri_classification_agent import (
    TriClassificationAgent,
    TriClassificationResult,
)
from apps.jmpartners.agents.tva_agent import TvaAgentResult
from apps.jmpartners.agents.tva_agent import run as run_tva
from apps.jmpartners.agents.verificateur_agent import (
    VerificateurAgent,
    VerificateurResult,
)

__all__ = ["OrchestratorResult", "run", "setup_nocturne_jobs"]

logger = logging.getLogger(__name__)

# Lettrage agent optionnel — peut ne pas exister en v2.2
try:
    from apps.jmpartners.agents.lettrage_agent import (
        LettrageAgent as _LettrageAgent,  # type: ignore[import]
    )
    _HAS_LETTRAGE = True
except ImportError:
    _LettrageAgent = None  # type: ignore[assignment,misc]
    _HAS_LETTRAGE = False


class OrchestratorResult(TypedDict):
    """Résultat d'un cycle complet de l'orchestrateur v2.2."""

    # Cycle diurne — chaîne documentaire
    collecte: CollecteResult | None
    ocr: OCRAgentResult | None
    tri: TriClassificationResult | None
    presaisie: PresaisieResult | None
    verificateur: VerificateurResult | None
    ged: GEDResult | None
    # Agents existants
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
        logger.error("Orchestrateur — erreur mail_handler : %s", exc)
        return None, relances

    for item in mail_result["emails"]:
        if item["type_demande"] != "document_manquant":
            continue
        if not item.get("contact_id"):
            continue
        logger.info(
            "Orchestrateur : email %s → document_manquant pour contact %s",
            item["message_id"],
            item["contact_id"],
        )

    return mail_result, relances


def run_document_relance_flow(
    dossier_id: str, dry_run: bool = False
) -> tuple[DocumentCheckerResult, RelanceResult]:
    """Flux complet : vérifie les documents d'un dossier et envoie la relance si nécessaire."""
    doc_result = check_docs(dossier_id, dry_run=dry_run)
    relance_result = send_relance(doc_result, dry_run=dry_run)
    return doc_result, relance_result


def run(dry_run: bool = False, cabinet_id: str = "jmpartners") -> OrchestratorResult:
    """Cycle diurne complet v2.2 : Collecte → OCR → Tri → Pré-saisie → Vérificateur → GED.

    Args:
        dry_run: Si True, simule le flux sans écrire en base ni envoyer d'alertes.
        cabinet_id: Identifiant du cabinet pour la clôture.
    """
    logger.info("Orchestrateur JM Partners v2.2 — démarrage (dry_run=%s)", dry_run)
    erreurs: list[str] = []

    # ── 1. Collecte documents (Outlook + Regate + PennyLane + manuel) ──────────
    collecte_result: CollecteResult | None = None
    try:
        collecte_result = CollecteAgent().run()
        logger.info(
            "collecte_agent : %d reçus, %d uploadés, %d doublons",
            collecte_result["documents_recus"],
            collecte_result["documents_uploades"],
            collecte_result["documents_dedupliques"],
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur collecte_agent : %s", exc)
        erreurs.append(f"collecte_agent: {exc}")

    # ── 2. OCR — extraction contenu (Claude Vision) ────────────────────────────
    ocr_result: OCRAgentResult | None = None
    try:
        ocr_result = OCRAgent().run()
        logger.info(
            "ocr_agent : %d traités, %d à trier, %d en attente",
            ocr_result["documents_traites"],
            ocr_result["documents_a_trier"],
            ocr_result["documents_en_attente"],
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur ocr_agent : %s", exc)
        erreurs.append(f"ocr_agent: {exc}")

    # ── 3. Tri & Classification ────────────────────────────────────────────────
    tri_result: TriClassificationResult | None = None
    try:
        tri_result = TriClassificationAgent().run()
        logger.info(
            "tri_agent : %d traités, %d qualifiés auto, %d en attente",
            tri_result["documents_traites"],
            tri_result["qualifies_auto"],
            tri_result["en_attente"],
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur tri_classification_agent : %s", exc)
        erreurs.append(f"tri_classification_agent: {exc}")

    # ── 4. Pré-saisie (Claude API + pgvector) ─────────────────────────────────
    presaisie_result: PresaisieResult | None = None
    try:
        presaisie_result = PresaisieAgent().run()
        logger.info(
            "presaisie_agent : %d traités, %d écritures proposées",
            presaisie_result["documents_traites"],
            presaisie_result["ecritures_proposees"],
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur presaisie_agent : %s", exc)
        erreurs.append(f"presaisie_agent: {exc}")

    # ── 5. Vérificateur (équilibre D/C, PCG, doublons) ────────────────────────
    verificateur_result: VerificateurResult | None = None
    try:
        verificateur_result = VerificateurAgent().run()
        logger.info(
            "verificateur_agent : %d vérifiées, lot_propre=%s, %d anomalies",
            verificateur_result["ecritures_verifiees"],
            verificateur_result["lot_propre"],
            len(verificateur_result["anomalies"]),
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur verificateur_agent : %s", exc)
        erreurs.append(f"verificateur_agent: {exc}")

    # ── 6. Lettrage (optionnel) ────────────────────────────────────────────────
    if _HAS_LETTRAGE:
        try:
            _LettrageAgent().run()  # type: ignore[union-attr]
            logger.info("lettrage_agent : terminé")
        except Exception as exc:
            logger.error("Orchestrateur — erreur lettrage_agent : %s", exc)
            erreurs.append(f"lettrage_agent: {exc}")
    else:
        logger.debug("Orchestrateur — lettrage_agent absent, étape ignorée")

    # ── 7. GED — archivage documents validés ──────────────────────────────────
    ged_result: GEDResult | None = None
    try:
        ged_result = GEDAgent().run()
        logger.info(
            "ged_agent : %d documents archivés",
            ged_result["documents_archives"],
        )
    except Exception as exc:
        logger.error("Orchestrateur — erreur ged_agent : %s", exc)
        erreurs.append(f"ged_agent: {exc}")

    # ── 8. Traitement emails entrants ─────────────────────────────────────────
    mail_result, relances = _handle_emails(dry_run)

    # ── 9. Surveillance TVA ───────────────────────────────────────────────────
    tva_result: TvaAgentResult | None = None
    try:
        tva_result = run_tva(dry_run=dry_run)
    except Exception as exc:
        logger.error("Orchestrateur — erreur tva_agent : %s", exc)
        erreurs.append(f"tva_agent: {exc}")

    # ── 10. Rapport échéances quotidien ───────────────────────────────────────
    echeance_result: EcheanceAgentResult | None = None
    try:
        echeance_result = run_echeances(dry_run=dry_run)
    except Exception as exc:
        logger.error("Orchestrateur — erreur echeance_agent : %s", exc)
        erreurs.append(f"echeance_agent: {exc}")

    # ── 11. Clôture comptable (fin de mois) ───────────────────────────────────
    cloture_result: ClotureResult | None = None
    if not dry_run:
        try:
            cloture_result = ClotureHandler(cabinet_id=cabinet_id).run()
        except Exception as exc:
            logger.error("Orchestrateur — erreur cloture_handler : %s", exc)
            erreurs.append(f"cloture_handler: {exc}")

    # ── 12. Alertes acomptes IS ───────────────────────────────────────────────
    acomptes_is: list[AcompteAlert] = []
    if not dry_run:
        try:
            acomptes_is = AcompteISAgent().run()
        except Exception as exc:
            logger.error("Orchestrateur — erreur acompte_is_agent : %s", exc)
            erreurs.append(f"acompte_is_agent: {exc}")

    # ── 13. Alertes bilan ─────────────────────────────────────────────────────
    bilans: list[BilanAlert] = []
    if not dry_run:
        try:
            bilans = BilanAgent().run()
        except Exception as exc:
            logger.error("Orchestrateur — erreur bilan_agent : %s", exc)
            erreurs.append(f"bilan_agent: {exc}")

    # ── 14. Alertes déclarations IS ───────────────────────────────────────────
    declarations_is: list[DeclarationISAlert] = []
    if not dry_run:
        try:
            declarations_is = DeclarationISAgent().run()
        except Exception as exc:
            logger.error("Orchestrateur — erreur declaration_is_agent : %s", exc)
            erreurs.append(f"declaration_is_agent: {exc}")

    # Hub notifications (service interne)
    _notification_agent = NotificationAgent()
    logger.debug("Orchestrateur — notification_agent disponible : %s", _notification_agent)

    logger.info(
        "Orchestrateur JM Partners v2.2 — cycle diurne terminé | "
        "collecte=%s ocr=%s tri=%s presaisie=%s verificateur=%s ged=%s erreurs=%d",
        collecte_result["documents_uploades"] if collecte_result else "n/a",
        ocr_result["documents_traites"] if ocr_result else "n/a",
        tri_result["qualifies_auto"] if tri_result else "n/a",
        presaisie_result["ecritures_proposees"] if presaisie_result else "n/a",
        verificateur_result["lot_propre"] if verificateur_result else "n/a",
        ged_result["documents_archives"] if ged_result else "n/a",
        len(erreurs),
    )

    return OrchestratorResult(
        collecte=collecte_result,
        ocr=ocr_result,
        tri=tri_result,
        presaisie=presaisie_result,
        verificateur=verificateur_result,
        ged=ged_result,
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


# ── Cycle nocturne APScheduler ────────────────────────────────────────────────


def _job_rpa_sage() -> None:
    """22h00 lun-ven — synchronisation Sage (stub)."""
    logger.info("job rpa_sage — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        result = RPASageAgent().run(mode="stub")
        logger.info(
            "job rpa_sage — terminé | ecritures_a_saisir=%d next=%s durée=%.1fs",
            result["ecritures_a_saisir"],
            result["next_agent"],
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job rpa_sage — erreur : %s", exc)


def _job_sync_fec() -> None:
    """23h00 lun-ven — import FEC depuis Sage."""
    logger.info("job sync_fec — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        result = MiroirSageAgent()._sync_fec()
        logger.info(
            "job sync_fec — terminé | nouvelles=%d durée=%.1fs",
            result["ecritures_nouvelles"],
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job sync_fec — erreur : %s", exc)


def _job_revision() -> None:
    """00h00 lun-ven — révision croisée nocturne."""
    logger.info("job revision — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        result = RevisionAgent().run()
        logger.info(
            "job revision — terminé | détectées=%d corrigées=%d en_attente=%d durée=%.1fs",
            result["anomalies_detectees"],
            result["anomalies_corrigees"],
            result["anomalies_en_attente"],
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job revision — erreur : %s", exc)


def _job_rapport_matinal() -> None:
    """06h00 lun-ven — rapport matinal collaborateurs."""
    logger.info("job rapport_matinal — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        result = MiroirSageAgent()._envoyer_rapport_matinal()
        logger.info(
            "job rapport_matinal — terminé | notifiés=%d dossiers=%d durée=%.1fs",
            result["collaborateurs_notifies"],
            result["dossiers_traites_nuit"],
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job rapport_matinal — erreur : %s", exc)


def _job_tva() -> None:
    """J-10 chaque mois — surveillance TVA."""
    logger.info("job tva — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        result = run_tva(dry_run=False)
        logger.info(
            "job tva — terminé | analysées=%d alertes=%d durée=%.1fs",
            result["declarations_analysees"],
            result["alertes_envoyees"],
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job tva — erreur : %s", exc)


def _job_acomptes_is() -> None:
    """Trimestriel — alertes acomptes IS."""
    logger.info("job acomptes_is — démarrage")
    t0 = datetime.now(timezone.utc)
    try:
        alertes = AcompteISAgent().run()
        logger.info(
            "job acomptes_is — terminé | alertes=%d durée=%.1fs",
            len(alertes),
            (datetime.now(timezone.utc) - t0).total_seconds(),
        )
    except Exception as exc:
        logger.error("job acomptes_is — erreur : %s", exc)


def setup_nocturne_jobs(scheduler: BackgroundScheduler) -> None:
    """Configure les jobs APScheduler du cycle nocturne.

    Args:
        scheduler: Instance BackgroundScheduler déjà instanciée (non démarrée).
    """
    # 22h00 lun-ven — RPA Sage stub
    scheduler.add_job(
        _job_rpa_sage,
        trigger="cron",
        day_of_week="mon-fri",
        hour=22,
        minute=0,
        id="rpa_sage",
        replace_existing=True,
    )
    # 23h00 lun-ven — Sync FEC
    scheduler.add_job(
        _job_sync_fec,
        trigger="cron",
        day_of_week="mon-fri",
        hour=23,
        minute=0,
        id="sync_fec",
        replace_existing=True,
    )
    # 00h00 lun-ven — Révision nocturne
    scheduler.add_job(
        _job_revision,
        trigger="cron",
        day_of_week="mon-fri",
        hour=0,
        minute=0,
        id="revision",
        replace_existing=True,
    )
    # 06h00 lun-ven — Rapport matinal
    scheduler.add_job(
        _job_rapport_matinal,
        trigger="cron",
        day_of_week="mon-fri",
        hour=6,
        minute=0,
        id="rapport_matinal",
        replace_existing=True,
    )
    # J-10 chaque mois — TVA (20 = J-10 du mois suivant, bonne approximation)
    scheduler.add_job(
        _job_tva,
        trigger="cron",
        day=20,
        hour=8,
        minute=0,
        id="tva_mensuelle",
        replace_existing=True,
    )
    # Trimestriel — Acomptes IS (1er jour des mois 3, 6, 9, 12)
    scheduler.add_job(
        _job_acomptes_is,
        trigger="cron",
        month="3,6,9,12",
        day=1,
        hour=7,
        minute=0,
        id="acomptes_is",
        replace_existing=True,
    )
    logger.info("Orchestrateur — %d jobs nocturnes configurés", 6)
