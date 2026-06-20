"""Diagnostic Telegram — valide le CHAT_ID et envoie un message de test."""

from __future__ import annotations

import logging
import os
import sys

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _get_credentials() -> tuple[str, str]:
    """Lit TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID depuis l'environnement.

    Returns:
        Tuple (bot_token, chat_id).

    Exits with code 1 si une variable est absente.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token:
        print("❌ TELEGRAM_BOT_TOKEN manquant dans l'environnement")
        sys.exit(1)
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID manquant dans l'environnement")
        sys.exit(1)

    return token, chat_id


def get_chat_info(token: str, chat_id: str) -> tuple[bool, str]:
    """Appelle getChat pour valider le CHAT_ID.

    Args:
        token: Token du bot Telegram.
        chat_id: Identifiant du chat cible.

    Returns:
        Tuple (succès, titre_du_chat ou message_erreur).
    """
    try:
        r = httpx.get(
            f"{TELEGRAM_API}/bot{token}/getChat",
            params={"chat_id": chat_id},
            timeout=10,
        )
        data = r.json()
        if data.get("ok"):
            chat = data.get("result", {})
            title = chat.get("title") or chat.get("first_name") or chat_id
            return True, title
        return False, data.get("description", "Erreur inconnue")
    except Exception as exc:
        return False, str(exc)


def send_test_message(token: str, chat_id: str) -> tuple[bool, str]:
    """Envoie un message de test dans le chat.

    Args:
        token: Token du bot Telegram.
        chat_id: Identifiant du chat cible.

    Returns:
        Tuple (succès, message_erreur_si_echec).
    """
    try:
        r = httpx.post(
            f"{TELEGRAM_API}/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "✅ Meta-Agent — test connexion Telegram OK",
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        data = r.json()
        if data.get("ok"):
            return True, ""
        return False, data.get("description", "Erreur inconnue")
    except Exception as exc:
        return False, str(exc)


def main() -> None:
    """Point d'entrée du script de diagnostic Telegram."""
    print("=== Diagnostic Telegram ===\n")

    token, chat_id = _get_credentials()
    all_ok = True

    ok, result = get_chat_info(token, chat_id)
    if ok:
        print(f"✅ Chat trouvé : {result!r}")
    else:
        print(f"❌ getChat échoué : {result}")
        all_ok = False

    if all_ok:
        ok, err = send_test_message(token, chat_id)
        if ok:
            print("✅ Message de test envoyé avec succès")
        else:
            print(f"❌ Envoi message échoué : {err}")
            all_ok = False

    print()
    if all_ok:
        print(f"✅ Telegram OK — chat: {result!r}")
        sys.exit(0)
    else:
        print("❌ Telegram KO — vérifier TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID")
        sys.exit(1)


if __name__ == "__main__":
    main()
