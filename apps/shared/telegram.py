"""Utilitaire Telegram partagé entre tous les agents."""

from __future__ import annotations

import logging
import os

import httpx

__all__ = ["send_telegram_message"]

logger = logging.getLogger(__name__)


def send_telegram_message(
    message: str,
    *,
    bot_token: str = "",
    chat_id: str = "",
) -> bool:
    """Envoie un message Telegram.

    Retourne False sans lever d'exception si les tokens sont absents ou en cas d'erreur.

    Args:
        message: Texte du message (tronqué à 4096 caractères).
        bot_token: Token du bot Telegram. Utilise TELEGRAM_BOT_TOKEN si vide.
        chat_id: ID du chat Telegram. Utilise TELEGRAM_CHAT_ID si vide.

    Returns:
        True si l'envoi réussit, False sinon.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    cid = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not cid:
        logger.warning("Telegram non configuré — message non envoyé")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": cid, "text": message[:4096], "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Telegram send error: %s", exc)
        return False
