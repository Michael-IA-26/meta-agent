"""Orchestrateur JM Partners.

Gère les déclencheurs entrants et distribue le travail aux 11 agents
spécialisés. Aucune logique métier ici — uniquement la coordination
et la gestion d'état via Supabase.

Déclencheurs :
  - on_nouveau_mail      — nouveau mail client reçu
  - on_document_recu     — pièce justificative déposée
  - on_etape_3_validee   — écritures validées par le gestionnaire
  - on_fin_de_mois       — clôture mensuelle (TVA, rapports)
  - on_echeance_proche   — échéance fiscale dans < N jours
  - on_exercice_clos     — exercice fiscal clôturé (liasse annuelle)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL", "")
_SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def _get_supabase_client() -> Any:
    """Return a Supabase client, or None if credentials are absent."""
    if not _SUPABASE_URL or not _SUPABASE_KEY:
        logger.warning("Supabase credentials absentes — mode offline")
        return None
    try:
        from supabase import create_client  # type: ignore[import-untyped]

        return create_client(_SUPABASE_URL, _SUPABASE_KEY)
    except Exception as exc:  # pragma: no cover
        logger.error("Impossible d'initialiser Supabase : %s", exc)
        return None


class Orchestrator:
    """Coordinateur principal JM Partners.

    Charge l'état depuis Supabase au démarrage, expose des méthodes
    par déclencheur, et délègue aux agents spécialisés.
    """

    def __init__(self, dry_run: bool = False) -> None:
        """Initialise l'orchestrateur.

        Args:
            dry_run: Si True, aucune écriture Supabase ni notification.
        """
        self.dry_run = dry_run
        self._supabase = _get_supabase_client()
        logger.info(
            "Orchestrateur JM Partners initialisé (dry_run=%s, supabase=%s)",
            dry_run,
            "ok" if self._supabase else "offline",
        )

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Exécution complète : vérifie toutes les files d'attente.

        Ordre d'exécution :
          1. Mails entrants non traités
          2. Documents reçus non analysés
          3. Échéances à < 7 jours
          4. Clôture mensuelle si dernier jour du mois
        """
        logger.info("Orchestrateur — démarrage du cycle complet")
        self._process_pending_mails()
        self._process_pending_documents()
        self._check_upcoming_deadlines(horizon_days=7)
        logger.info("Orchestrateur — cycle terminé")

    # ------------------------------------------------------------------
    # Déclencheurs publics
    # ------------------------------------------------------------------

    def on_nouveau_mail(self, mail: dict[str, Any]) -> None:
        """Déclenché à la réception d'un mail client.

        Args:
            mail: Payload brut (from, subject, body, attachments).
        """
        dossier_id = mail.get("dossier_id", "inconnu")
        logger.info("on_nouveau_mail — dossier=%s sujet=%r", dossier_id, mail.get("subject"))
        # TODO: agent mail_handler.classify(mail)
        # TODO: agent document_receiver.save_attachments(mail)
        # TODO: agent notifier.ack_client(mail)
        self._write_journal(
            dossier_id=dossier_id,
            evenement="nouveau_mail",
            payload=mail,
        )

    def on_document_recu(self, document: dict[str, Any]) -> None:
        """Déclenché après dépôt d'une pièce justificative.

        Args:
            document: {id, dossier_id, type_document, storage_path}.
        """
        document_id = document.get("id", "inconnu")
        dossier_id = document.get("dossier_id", "inconnu")
        logger.info("on_document_recu — document=%s dossier=%s", document_id, dossier_id)
        # TODO: agent document_analyzer.extract(document)
        # TODO: agent ecriture_generator.propose(document)
        self._write_journal(
            dossier_id=dossier_id,
            evenement="document_recu",
            payload=document,
        )

    def on_etape_3_validee(self, dossier_id: str) -> None:
        """Déclenché quand le gestionnaire valide les écritures (étape 3).

        Args:
            dossier_id: UUID du dossier concerné.
        """
        logger.info("on_etape_3_validee — dossier=%s", dossier_id)
        # TODO: agent tva_declarator.prepare(dossier_id)
        # TODO: agent is_tracker.update(dossier_id)
        # TODO: agent report_builder.refresh(dossier_id)
        # TODO: agent notifier.notify_gestionnaire(dossier_id, "etape_3_ok")
        self._set_dossier_etape(dossier_id, etape=4)
        self._write_journal(
            dossier_id=dossier_id,
            evenement="etape_3_validee",
            payload={"dossier_id": dossier_id},
        )

    def on_fin_de_mois(self, annee: int, mois: int) -> None:
        """Déclenché en fin de mois pour clôture mensuelle.

        Args:
            annee: Année (ex. 2026).
            mois:  Mois 1-12.
        """
        periode = f"{annee:04d}-{mois:02d}"
        logger.info("on_fin_de_mois — periode=%s", periode)
        # TODO: agent tva_declarator.run_batch(annee, mois)
        # TODO: agent report_builder.generate_monthly(annee, mois)
        # TODO: agent notifier.send_monthly_summary(periode)

    def on_echeance_proche(self, echeance: dict[str, Any]) -> None:
        """Déclenché quand une échéance fiscale approche.

        Args:
            echeance: {dossier_id, type, date_limite, jours_restants}.
        """
        dossier_id = echeance.get("dossier_id", "inconnu")
        type_echeance = echeance.get("type", "inconnu")
        jours = echeance.get("jours_restants", 0)
        logger.info(
            "on_echeance_proche — dossier=%s type=%s jours_restants=%d",
            dossier_id,
            type_echeance,
            jours,
        )
        # TODO: agent deadline_monitor.escalate(echeance)
        # TODO: agent notifier.alert_gestionnaire(echeance)

    def on_exercice_clos(self, dossier_id: str, exercice: int) -> None:
        """Déclenché à la clôture de l'exercice fiscal.

        Args:
            dossier_id: UUID du dossier.
            exercice:   Année de l'exercice clôturé (ex. 2025).
        """
        logger.info("on_exercice_clos — dossier=%s exercice=%d", dossier_id, exercice)
        # TODO: agent tva_declarator.close_year(dossier_id, exercice)
        # TODO: agent is_tracker.close_year(dossier_id, exercice)
        # TODO: agent report_builder.generate_annual(dossier_id, exercice)
        # TODO: agent validation_agent.final_review(dossier_id, exercice)
        self._write_journal(
            dossier_id=dossier_id,
            evenement="exercice_clos",
            payload={"exercice": exercice},
        )

    # ------------------------------------------------------------------
    # Processus internes
    # ------------------------------------------------------------------

    def _process_pending_mails(self) -> None:
        """Relance le traitement des mails non encore routés."""
        logger.debug("_process_pending_mails — lecture Supabase")
        # TODO: query documents WHERE statut='recu' AND type='mail'
        #       pour chaque entrée → on_nouveau_mail()

    def _process_pending_documents(self) -> None:
        """Relance l'analyse des documents reçus et non encore traités."""
        logger.debug("_process_pending_documents — lecture Supabase")
        # TODO: query documents WHERE statut='recu'
        #       pour chaque entrée → on_document_recu()

    def _check_upcoming_deadlines(self, horizon_days: int = 7) -> None:
        """Déclenche des alertes pour les échéances dans < horizon_days jours."""
        logger.debug("_check_upcoming_deadlines — horizon=%d jours", horizon_days)
        # TODO: query declarations_tva WHERE statut IN ('a_preparer','en_cours')
        #         AND date_limite <= now() + interval
        # TODO: query acomptes_is WHERE statut IN ('planifie')
        #         AND date_echeance <= now() + interval
        # Pour chaque résultat → on_echeance_proche()

    # ------------------------------------------------------------------
    # Helpers Supabase
    # ------------------------------------------------------------------

    def _write_journal(
        self,
        dossier_id: str,
        evenement: str,
        payload: dict[str, Any],
    ) -> None:
        """Insère une ligne de journal d'orchestration dans Supabase.

        Silencieux en cas d'erreur pour ne pas bloquer le traitement principal.
        """
        if self.dry_run or not self._supabase:
            logger.debug(
                "[journal skip] dossier=%s evenement=%s", dossier_id, evenement
            )
            return
        try:
            self._supabase.table("journaux").insert(
                {
                    "dossier_id": dossier_id,
                    "evenement": evenement,
                    "payload": payload,
                }
            ).execute()
        except Exception as exc:
            logger.warning(
                "_write_journal échoue (dossier=%s evenement=%s) : %s",
                dossier_id,
                evenement,
                exc,
            )

    def _set_dossier_etape(self, dossier_id: str, etape: int) -> None:
        """Met à jour l'étape courante d'un dossier dans Supabase."""
        if self.dry_run or not self._supabase:
            logger.debug(
                "[etape skip] dossier=%s etape=%d", dossier_id, etape
            )
            return
        try:
            self._supabase.table("dossiers").update(
                {"etape_courante": etape}
            ).eq("id", dossier_id).execute()
            logger.info("Dossier %s → étape %d", dossier_id, etape)
        except Exception as exc:
            logger.warning(
                "_set_dossier_etape échoue (dossier=%s) : %s", dossier_id, exc
            )
