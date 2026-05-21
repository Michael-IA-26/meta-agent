"""Agent: envoie une alerte Telegram pour 1 lead qualifié → bool."""
import logging
import os
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)

_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


class NotifyInput(TypedDict):
    """Lead fields required to format and send a Telegram alert."""

    siren: str | None
    denomination: str
    commune: str | None
    dept: str
    code_naf: str | None
    date_creation: str | None
    score: int
    signal_type: str
    scoring_details: list[str]
    dirigeant_nom: str
    dirigeant_prenom: str
    dirigeant_email: str
    site_web: str
    capital_social: int | None


def _format_message(params: NotifyInput) -> str:
    """Build the Telegram Markdown alert message for a qualified lead."""
    lines = [
        "🎯 *Nouveau lead LeadCommercial*",
        "",
        f"*{params['denomination']}*",
        f"📍 {params['commune']} ({params['dept']})",
        f"🏭 NAF : {params['code_naf'] or 'N/A'}",
        f"📅 Créé le : {params['date_creation']}",
        f"🔢 SIREN : {params['siren']}",
    ]
    nom = params["dirigeant_nom"]
    prenom = params["dirigeant_prenom"]
    if nom or prenom:
        lines.append(f"👤 Dirigeant : {prenom} {nom}".strip())
    if params["dirigeant_email"]:
        lines.append(f"📧 Email : {params['dirigeant_email']}")
    if params["site_web"]:
        lines.append(f"🌐 Site : {params['site_web']}")
    if params["capital_social"] is not None:
        lines.append(f"💰 Capital : {params['capital_social']} €")
    lines += [
        "",
        f"⭐ Score : *{params['score']}/100*",
        f"📊 Signal : {params['signal_type']}",
        "",
        f"_Détail scoring : {', '.join(params['scoring_details'])}_",
    ]
    return "\n".join(lines)


def notify_lead(params: NotifyInput) -> bool:
    """Send a Telegram Markdown alert for a qualified lead.

    Returns True on success, False if Telegram is not configured or on error.
    """
    if not _BOT_TOKEN or not _CHAT_ID:
        logger.warning(
            "Telegram non configure — TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant"
        )
        return False

    message = _format_message(params)
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{_BOT_TOKEN}/sendMessage",
            json={"chat_id": _CHAT_ID, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        r.raise_for_status()
        logger.info("telegram_notifier: alerte envoyee pour %s", params["denomination"])
        return True
    except Exception as exc:
        logger.error(
            "telegram_notifier: erreur pour %s: %s", params["denomination"], exc
        )
        return False
