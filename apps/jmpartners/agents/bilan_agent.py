"""Agent bilan_agent — alertes J-30/J-15/J-7 avant deadline bilan comptable."""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict, cast

import httpx
from supabase import Client, create_client

__all__ = ["BilanAlert", "BilanAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
CABINET_ID = os.getenv("CABINET_ID", "")

HORIZONS_ALERTE = [30, 15, 7]

# Documents attendus pour un bilan
DOCUMENTS_BILAN = [
    "grand_livre",
    "balance",
    "factures_achats",
    "factures_ventes",
    "releves_bancaires",
]


class BilanAlert(TypedDict):
    """Alerte pour un dossier bilan."""

    dossier_id: str
    contact_nom: str
    deadline: str
    jours_restants: int
    documents_manquants: list[str]
    alerte_envoyee: bool


class BilanAgent:
    """Surveille les dossiers bilan et envoie des alertes avant deadline."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                raise ValueError("SUPABASE_URL et SUPABASE_SERVICE_KEY sont requis — configure Doppler")
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _fetch_dossiers_bilan(self) -> list[dict]:
        """Récupère les dossiers bilan en cours pour le cabinet courant."""
        try:
            query = (
                self._get_supabase()
                .table("dossiers")
                .select(
                    "id, contact_id, deadline, responsable_email, contacts(nom, email)"
                )
                .eq("type", "bilan")
                .eq("statut", "en_cours")
            )
            if CABINET_ID:
                query = query.eq("cabinet_id", CABINET_ID)
            resp = query.execute()
            return [cast(dict, row) for row in (resp.data or [])]
        except Exception as exc:
            logger.error(f"bilan_agent — erreur fetch dossiers : {exc}")
            return []

    def _check_documents(self, dossier_id: str) -> list[str]:
        """Retourne la liste des documents manquants pour un dossier bilan."""
        try:
            resp = (
                self._get_supabase()
                .table("documents")
                .select("nom_document, present")
                .eq("dossier_id", dossier_id)
                .execute()
            )
            presents: set[str] = set()
            for row in resp.data or []:
                r = cast(dict, row)
                if r.get("present"):
                    presents.add(r["nom_document"])
            return [doc for doc in DOCUMENTS_BILAN if doc not in presents]
        except Exception as exc:
            logger.error(f"bilan_agent — erreur check documents {dossier_id} : {exc}")
            return list(DOCUMENTS_BILAN)

    def _send_alerte(self, alert: BilanAlert) -> bool:
        """Envoie email SMTP + Telegram pour l'alerte bilan."""
        jours = alert["jours_restants"]
        contact = alert["contact_nom"]
        deadline = alert["deadline"]
        manquants = alert["documents_manquants"]
        dossier_id = alert["dossier_id"]

        manquants_str = "\n".join(f"- {m}" for m in manquants)
        message = (
            f"Alerte Bilan — {contact}\n"
            f"Dossier : {dossier_id}\n"
            f"Deadline : {deadline} (J-{jours})\n"
            f"Documents manquants :\n{manquants_str}"
        )
        sujet = f"Bilan J-{jours} — {contact}"

        ok_email = self._send_email(sujet, message)
        ok_telegram = self._send_telegram(message)
        return ok_email or ok_telegram

    def _send_email(self, sujet: str, corps: str) -> bool:
        """Envoie un email via SMTP."""
        if not SMTP_USER or not SMTP_PASS:
            logger.warning("bilan_agent — SMTP non configuré, email non envoyé")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = SMTP_USER
            msg["To"] = SMTP_USER
            msg["Subject"] = sujet
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [SMTP_USER], msg.as_string())
            return True
        except Exception as exc:
            logger.error(f"bilan_agent — erreur SMTP : {exc}")
            return False

    def _send_telegram(self, message: str) -> bool:
        """Envoie une alerte Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("bilan_agent — Telegram non configuré, alerte non envoyée")
            return False
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": message[:4096],
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            r.raise_for_status()
            return True
        except Exception as exc:
            logger.error(f"bilan_agent — erreur Telegram : {exc}")
            return False

    def _log_journal(
        self, dossier_id: str, action: str, message: str, niveau: str = "info"
    ) -> None:
        """Logue une action dans la table journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "cabinet_id": CABINET_ID or None,
                    "dossier_id": dossier_id,
                    "agent": "bilan_agent",
                    "action": action,
                    "message": message[:500],
                    "niveau": niveau,
                }
            ).execute()
        except Exception as exc:
            logger.error(
                f"bilan_agent — erreur log journal dossier {dossier_id} : {exc}"
            )

    def run(self) -> list[BilanAlert]:
        """Exécute le cycle d'alertes bilan.

        Returns:
            Liste des BilanAlert générées.
        """
        logger.info("bilan_agent — démarrage")
        today = date.today()
        dossiers = self._fetch_dossiers_bilan()
        logger.info(f"bilan_agent : {len(dossiers)} dossier(s) bilan en cours")

        alerts: list[BilanAlert] = []

        for dossier in dossiers:
            dossier_id: str = dossier["id"]
            raw_deadline = dossier.get("deadline")
            if not raw_deadline:
                logger.warning(
                    f"bilan_agent : dossier {dossier_id} sans deadline, ignoré"
                )
                continue

            try:
                deadline_date = date.fromisoformat(str(raw_deadline))
            except ValueError:
                logger.warning(
                    f"bilan_agent : deadline invalide pour dossier {dossier_id}"
                )
                continue

            jours_restants = (deadline_date - today).days
            if jours_restants not in HORIZONS_ALERTE:
                continue

            # Résolution du nom du contact
            contact_nom = "Client inconnu"
            contact_data = dossier.get("contacts")
            if isinstance(contact_data, dict):
                contact_nom = contact_data.get("nom") or contact_nom
            elif isinstance(contact_data, list) and contact_data:
                contact_nom = cast(dict, contact_data[0]).get("nom") or contact_nom

            documents_manquants = self._check_documents(dossier_id)

            alert = BilanAlert(
                dossier_id=dossier_id,
                contact_nom=contact_nom,
                deadline=deadline_date.isoformat(),
                jours_restants=jours_restants,
                documents_manquants=documents_manquants,
                alerte_envoyee=False,
            )

            alerte_envoyee = self._send_alerte(alert)
            alert["alerte_envoyee"] = alerte_envoyee

            niveau = "info" if alerte_envoyee else "warning"
            self._log_journal(
                dossier_id,
                "alerte_bilan",
                (
                    f"Alerte J-{jours_restants} pour {contact_nom} — "
                    f"{'envoyée' if alerte_envoyee else 'échec envoi'}"
                ),
                niveau=niveau,
            )

            alerts.append(alert)
            logger.info(
                f"bilan_agent : alerte {'envoyée' if alerte_envoyee else 'échec'} "
                f"→ {contact_nom} J-{jours_restants}"
            )

        logger.info(f"bilan_agent terminé : {len(alerts)} alerte(s)")
        return alerts
