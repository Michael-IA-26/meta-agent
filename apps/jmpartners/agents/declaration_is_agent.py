"""Agent declaration_is_agent — alertes J-30/J-15/J-7 avant échéances IS."""

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

__all__ = ["DeclarationISAlert", "DeclarationISAgent"]

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


class DeclarationISAlert(TypedDict):
    """Alerte pour une échéance IS."""

    dossier_id: str
    siren: str
    raison_sociale: str
    echeance_is: str
    jours_restants: int
    elements_disponibles: list[str]
    alerte_envoyee: bool


class DeclarationISAgent:
    """Surveille les échéances IS et envoie des alertes avant deadline."""

    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _fetch_echeances_is(self) -> list[dict]:
        """Récupère les échéances IS non payées pour le cabinet courant.

        Joint les dossiers pour récupérer siren et raison_sociale.
        """
        try:
            query = (
                self._get_supabase()
                .table("acomptes_is")
                .select(
                    "id, dossier_id, echeance, montant_estime, statut, "
                    "dossiers(cabinet_id, siren, raison_sociale)"
                )
                .neq("statut", "paye")
            )
            resp = query.execute()
            rows = [cast(dict, row) for row in (resp.data or [])]

            # Filtre par cabinet_id si défini
            if CABINET_ID:
                filtered = []
                for row in rows:
                    dossier_data = row.get("dossiers") or {}
                    if isinstance(dossier_data, list):
                        dossier_data = dossier_data[0] if dossier_data else {}
                    if cast(dict, dossier_data).get("cabinet_id") == CABINET_ID:
                        filtered.append(row)
                return filtered
            return rows
        except Exception as exc:
            logger.error(f"declaration_is_agent — erreur fetch échéances IS : {exc}")
            return []

    def _get_elements_disponibles(self, dossier_id: str) -> list[str]:
        """Retourne les noms des documents présents dans le dossier."""
        try:
            resp = (
                self._get_supabase()
                .table("documents")
                .select("nom_document, present")
                .eq("dossier_id", dossier_id)
                .eq("present", True)
                .execute()
            )
            return [cast(dict, row)["nom_document"] for row in (resp.data or [])]
        except Exception as exc:
            logger.error(
                f"declaration_is_agent — erreur fetch documents "
                f"dossier {dossier_id} : {exc}"
            )
            return []

    def _send_alerte(self, alert: DeclarationISAlert) -> bool:
        """Envoie email SMTP + Telegram pour l'alerte IS."""
        jours = alert["jours_restants"]
        raison = alert["raison_sociale"]
        siren = alert["siren"]
        echeance = alert["echeance_is"]
        dossier_id = alert["dossier_id"]

        message = (
            f"Alerte IS — {raison} ({siren})\n"
            f"Dossier : {dossier_id}\n"
            f"Échéance IS : {echeance} (J-{jours})\n"
            f"Éléments disponibles : {len(alert['elements_disponibles'])} document(s)"
        )
        sujet = f"Déclaration IS J-{jours} — {raison}"

        ok_email = self._send_email(sujet, message)
        ok_telegram = self._send_telegram(message)
        return ok_email or ok_telegram

    def _send_email(self, sujet: str, corps: str) -> bool:
        """Envoie un email via SMTP."""
        if not SMTP_USER or not SMTP_PASS:
            logger.warning(
                "declaration_is_agent — SMTP non configuré, email non envoyé"
            )
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
            logger.error(f"declaration_is_agent — erreur SMTP : {exc}")
            return False

    def _send_telegram(self, message: str) -> bool:
        """Envoie une alerte Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning(
                "declaration_is_agent — Telegram non configuré, alerte non envoyée"
            )
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
            logger.error(f"declaration_is_agent — erreur Telegram : {exc}")
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
                    "agent": "declaration_is_agent",
                    "action": action,
                    "message": message[:500],
                    "niveau": niveau,
                }
            ).execute()
        except Exception as exc:
            logger.error(
                f"declaration_is_agent — erreur log journal "
                f"dossier {dossier_id} : {exc}"
            )

    def run(self) -> list[DeclarationISAlert]:
        """Exécute le cycle d'alertes IS.

        Returns:
            Liste des DeclarationISAlert générées.
        """
        logger.info("declaration_is_agent — démarrage")
        today = date.today()
        echeances = self._fetch_echeances_is()
        logger.info(
            f"declaration_is_agent : {len(echeances)} échéance(s) IS non payée(s)"
        )

        alerts: list[DeclarationISAlert] = []

        for echeance_row in echeances:
            dossier_id: str = echeance_row.get("dossier_id", "")
            raw_echeance = echeance_row.get("echeance")
            if not raw_echeance:
                logger.warning(
                    f"declaration_is_agent : échéance sans date pour "
                    f"dossier {dossier_id}, ignorée"
                )
                continue

            try:
                echeance_date = date.fromisoformat(str(raw_echeance))
            except ValueError:
                logger.warning(
                    f"declaration_is_agent : date invalide '{raw_echeance}' "
                    f"pour dossier {dossier_id}"
                )
                continue

            jours_restants = (echeance_date - today).days
            if jours_restants not in HORIZONS_ALERTE:
                continue

            # Résolution siren / raison_sociale via le join dossiers
            dossier_data = echeance_row.get("dossiers") or {}
            if isinstance(dossier_data, list):
                dossier_data = dossier_data[0] if dossier_data else {}
            dossier_info = cast(dict, dossier_data)
            siren: str = dossier_info.get("siren") or ""
            raison_sociale: str = dossier_info.get("raison_sociale") or "N/A"

            elements_disponibles = self._get_elements_disponibles(dossier_id)

            alert = DeclarationISAlert(
                dossier_id=dossier_id,
                siren=siren,
                raison_sociale=raison_sociale,
                echeance_is=echeance_date.isoformat(),
                jours_restants=jours_restants,
                elements_disponibles=elements_disponibles,
                alerte_envoyee=False,
            )

            alerte_envoyee = self._send_alerte(alert)
            alert["alerte_envoyee"] = alerte_envoyee

            niveau = "info" if alerte_envoyee else "warning"
            self._log_journal(
                dossier_id,
                "alerte_declaration_is",
                (
                    f"Alerte IS J-{jours_restants} pour {raison_sociale} — "
                    f"{'envoyée' if alerte_envoyee else 'échec envoi'}"
                ),
                niveau=niveau,
            )

            alerts.append(alert)
            logger.info(
                f"declaration_is_agent : alerte "
                f"{'envoyée' if alerte_envoyee else 'échec'} "
                f"→ {raison_sociale} J-{jours_restants}"
            )

        logger.info(f"declaration_is_agent terminé : {len(alerts)} alerte(s)")
        return alerts
