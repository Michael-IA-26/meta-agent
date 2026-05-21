"""Agent notification_agent — hub de notifications avec déduplication 24h."""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TypedDict, cast

import httpx
from postgrest import CountMethod
from supabase import Client, create_client

__all__ = ["NotificationPayload", "NotificationAgent"]

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

# Urgences qui déclenchent Telegram immédiat
URGENCES_TELEGRAM = {"J-3"}
# Urgences digest : accumule, pas de doublon dans 24h
URGENCES_DIGEST = {"J-15", "J-30"}


class NotificationPayload(TypedDict):
    """Payload d'une notification à envoyer."""

    dossier_id: str
    type: str  # "bilan" | "declaration_is" | "relance" | "cloture"
    urgence: str  # "J-3" | "J-7" | "J-15" | "J-30"
    message: str
    destinataire_email: str
    destinataire_nom: str


class NotificationAgent:
    """Hub de notifications avec déduplication 24h et routing par urgence."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _is_duplicate(self, dossier_id: str, action: str) -> bool:
        """Vérifie si une notification similaire a été envoyée dans les 24h.

        Interroge la table journaux pour détecter les doublons.
        """
        seuil = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
        try:
            resp = (
                self._get_supabase()
                .table("journaux")
                .select("id", count=CountMethod.exact)
                .eq("dossier_id", dossier_id)
                .eq("action", action)
                .gte("created_at", seuil)
                .execute()
            )
            count = resp.count if resp.count is not None else len(resp.data or [])
            return count > 0
        except Exception as exc:
            logger.warning(
                f"notification_agent — erreur vérification doublon "
                f"dossier {dossier_id} : {exc}"
            )
            return False

    def _log_journal(
        self, payload: NotificationPayload, action: str, statut: str
    ) -> None:
        """Logue l'envoi de notification dans journaux."""
        try:
            self._get_supabase().table("journaux").insert(
                {
                    "cabinet_id": CABINET_ID or None,
                    "dossier_id": payload["dossier_id"],
                    "agent": "notification_agent",
                    "action": action,
                    "message": payload["message"][:500],
                    "niveau": "info" if statut == "ok" else "warning",
                }
            ).execute()
        except Exception as exc:
            logger.error(f"notification_agent — erreur log journal : {exc}")

    def _send_email(self, destinataire: str, sujet: str, corps: str) -> bool:
        """Envoie un email via SMTP."""
        if not SMTP_USER or not SMTP_PASS:
            logger.warning("notification_agent — SMTP non configuré")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = SMTP_USER
            msg["To"] = destinataire
            msg["Subject"] = sujet
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(SMTP_USER, [destinataire], msg.as_string())
            return True
        except Exception as exc:
            logger.error(
                f"notification_agent — erreur SMTP vers {destinataire} : {exc}"
            )
            return False

    def _send_telegram(self, message: str) -> bool:
        """Envoie un message Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("notification_agent — Telegram non configuré")
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
            logger.error(f"notification_agent — erreur Telegram : {exc}")
            return False

    def send(self, alert: NotificationPayload) -> bool:
        """Envoie une notification en appliquant le routing par urgence.

        Routing :
        - J-3  → Telegram immédiat + email
        - J-7  → email seul
        - J-15 / J-30 → email digest (déduplication 24h)

        Returns:
            True si au moins un canal a réussi, False sinon.
        """
        dossier_id = alert["dossier_id"]
        urgence = alert["urgence"]
        action = f"notification_{alert['type']}_{urgence}"

        # Déduplication pour les digests
        if urgence in URGENCES_DIGEST:
            if self._is_duplicate(dossier_id, action):
                logger.info(
                    f"notification_agent — doublon 24h ignoré "
                    f"(dossier={dossier_id}, urgence={urgence})"
                )
                return False

        sujet = (
            f"[{urgence}] {alert['type'].replace('_', ' ').title()} — "
            f"{alert['destinataire_nom']}"
        )
        corps = alert["message"]
        destinataire = alert["destinataire_email"]

        ok = False

        if urgence in URGENCES_TELEGRAM:
            # J-3 : Telegram immédiat + email
            ok_tg = self._send_telegram(corps)
            ok_mail = self._send_email(destinataire, sujet, corps)
            ok = ok_tg or ok_mail
        elif urgence == "J-7":
            # J-7 : email seul
            ok = self._send_email(destinataire, sujet, corps)
        else:
            # J-15 / J-30 : email digest
            ok = self._send_email(destinataire, sujet, corps)

        statut = "ok" if ok else "erreur"
        self._log_journal(alert, action, statut)

        logger.info(
            f"notification_agent : notification {urgence} "
            f"{'envoyée' if ok else 'échec'} → {destinataire}"
        )
        return ok

    def send_batch(self, alerts: list[NotificationPayload]) -> list[bool]:
        """Envoie une liste de notifications.

        Args:
            alerts: Liste de NotificationPayload à traiter.

        Returns:
            Liste de bool, un par alerte, True si envoi réussi.
        """
        results: list[bool] = []
        for alert in alerts:
            try:
                results.append(self.send(alert))
            except Exception as exc:
                logger.error(
                    f"notification_agent — erreur batch pour dossier "
                    f"{alert.get('dossier_id')} : {exc}"
                )
                results.append(False)
        return results


def _build_action_key(payload: NotificationPayload) -> str:
    """Retourne la clé d'action pour la déduplication."""
    return f"notification_{payload['type']}_{payload['urgence']}"


def _resolve_contact_email(
    supabase: Client, contact_id: str
) -> tuple[str | None, str | None]:
    """Résout l'email et le nom d'un contact depuis Supabase."""
    try:
        resp = (
            supabase.table("contacts")
            .select("email, nom")
            .eq("id", contact_id)
            .single()
            .execute()
        )
        if resp.data:
            row = cast(dict, resp.data)
            return row.get("email"), row.get("nom")
    except Exception as exc:
        logger.warning(
            f"notification_agent — erreur résolution contact {contact_id} : {exc}"
        )
    return None, None
