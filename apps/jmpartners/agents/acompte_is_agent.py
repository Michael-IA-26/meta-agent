"""Agent acompte_is_agent — alertes J-15/J-7/J-3 avant échéances IS."""

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

__all__ = ["AcompteAlert", "AcompteISAgent"]

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

HORIZONS_ALERTE = [15, 7, 3]

ECHEANCES_IS = [
    (3, 15),
    (6, 15),
    (9, 15),
    (12, 15),
]


class AcompteAlert(TypedDict):
    siren: str
    raison_sociale: str
    echeance: str
    jours_restants: int
    montant_estime: float
    alerte_envoyee: bool


def _prochaine_echeance_is(today: date) -> date | None:
    """Retourne la prochaine échéance IS à partir d'aujourd'hui."""
    for mois, jour in ECHEANCES_IS:
        echeance = date(today.year, mois, jour)
        if echeance >= today:
            return echeance
    return date(today.year + 1, ECHEANCES_IS[0][0], ECHEANCES_IS[0][1])


def _echeances_dans_horizon(today: date, horizon: int) -> list[date]:
    """Retourne toutes les échéances IS dans les N prochains jours."""
    echeances = []
    for mois, jour in ECHEANCES_IS:
        for annee in [today.year, today.year + 1]:
            echeance = date(annee, mois, jour)
            delta = (echeance - today).days
            if 0 <= delta <= horizon:
                echeances.append(echeance)
    return echeances


class AcompteISAgent:
    def __init__(self) -> None:
        self._supabase: Client | None = None

    def _get_supabase(self) -> Client:
        if self._supabase is None:
            self._supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return self._supabase

    def _fetch_dossiers(self) -> list[dict]:
        try:
            resp = (
                self._get_supabase()
                .table("dossiers")
                .select("id, siren, raison_sociale, montant_is_estime, statut")
                .neq("statut", "archive")
                .execute()
            )
            return [cast(dict, row) for row in (resp.data or [])]
        except Exception as exc:
            logger.error(f"Erreur fetch dossiers IS : {exc}")
            return []

    def _send_email(self, destinataire: str, sujet: str, corps: str) -> bool:
        if not SMTP_USER or not SMTP_PASSWORD:
            logger.warning("SMTP non configuré — email IS non envoyé")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = SMTP_USER
            msg["To"] = destinataire
            msg["Subject"] = sujet
            msg.attach(MIMEText(corps, "plain", "utf-8"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, [destinataire], msg.as_string())
            return True
        except Exception as exc:
            logger.error(f"Erreur SMTP IS vers {destinataire} : {exc}")
            return False

    def _send_telegram(self, message: str) -> bool:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram non configuré — alerte IS non envoyée")
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
            logger.error(f"Erreur Telegram IS : {exc}")
            return False

    def run(self) -> list[AcompteAlert]:
        today = date.today()
        logger.info("acompte_is_agent — démarrage")

        echeances_proches = _echeances_dans_horizon(today, max(HORIZONS_ALERTE))
        if not echeances_proches:
            logger.info("acompte_is_agent : aucune échéance IS dans l'horizon")
            return []

        dossiers = self._fetch_dossiers()
        alerts: list[AcompteAlert] = []

        for echeance in echeances_proches:
            jours_restants = (echeance - today).days
            if jours_restants not in HORIZONS_ALERTE:
                continue

            for dossier in dossiers:
                siren: str = dossier.get("siren", "")
                raison_sociale: str = dossier.get("raison_sociale", "N/A")
                montant_estime: float = float(dossier.get("montant_is_estime") or 0.0)

                message = (
                    f"Acompte IS — {raison_sociale} ({siren})\n"
                    f"Échéance : {echeance.isoformat()} (J-{jours_restants})\n"
                    f"Montant estimé : {montant_estime:,.0f} €"
                )
                sujet = f"Acompte IS J-{jours_restants} — {raison_sociale}"

                ok_email = self._send_email(SMTP_USER, sujet, message)
                ok_telegram = self._send_telegram(message)
                alerte_envoyee = ok_email or ok_telegram

                alerts.append(
                    AcompteAlert(
                        siren=siren,
                        raison_sociale=raison_sociale,
                        echeance=echeance.isoformat(),
                        jours_restants=jours_restants,
                        montant_estime=montant_estime,
                        alerte_envoyee=alerte_envoyee,
                    )
                )
                logger.info(
                    f"acompte_is_agent : alerte {'envoyée' if alerte_envoyee else 'échec'} "
                    f"→ {raison_sociale} J-{jours_restants}"
                )

        logger.info(f"acompte_is_agent terminé : {len(alerts)} alerte(s)")
        return alerts
