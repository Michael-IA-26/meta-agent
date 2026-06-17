"""Microsoft Graph mail integration — app-only OAuth2 (client credentials).

Env vars required:
    GRAPH_TENANT_ID      Azure AD tenant ID
    GRAPH_CLIENT_ID      App registration client ID
    GRAPH_CLIENT_SECRET  App registration client secret
    GRAPH_MAILBOX        Mailbox UPN, e.g. compta@jmpartners.fr
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_TOKEN_URL_TMPL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"


def _configured() -> bool:
    return bool(
        os.getenv("GRAPH_TENANT_ID")
        and os.getenv("GRAPH_CLIENT_ID")
        and os.getenv("GRAPH_CLIENT_SECRET")
    )


def get_token() -> str:
    """Obtient un access token via client credentials (app-only OAuth2).

    Returns:
        Bearer token string.

    Raises:
        RuntimeError: if Graph env vars are missing or the request fails.
    """
    import httpx

    tenant_id = os.getenv("GRAPH_TENANT_ID", "")
    client_id = os.getenv("GRAPH_CLIENT_ID", "")
    client_secret = os.getenv("GRAPH_CLIENT_SECRET", "")
    if not (tenant_id and client_id and client_secret):
        raise RuntimeError("GRAPH_TENANT_ID / GRAPH_CLIENT_ID / GRAPH_CLIENT_SECRET manquants")

    url = _TOKEN_URL_TMPL.format(tenant=tenant_id)
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    resp = httpx.post(url, data=data, timeout=15)
    resp.raise_for_status()
    return str(resp.json()["access_token"])


def fetch_unread() -> list[dict[str, Any]]:
    """Récupère les messages non lus dans la boîte GRAPH_MAILBOX.

    Returns:
        Liste de messages Graph (valeurs brutes JSON de l'API).
    """
    import httpx

    mailbox = os.getenv("GRAPH_MAILBOX", "")
    if not mailbox:
        raise RuntimeError("GRAPH_MAILBOX manquant")

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    url = (
        f"{_GRAPH_BASE}/users/{mailbox}/mailFolders/inbox/messages"
        "?$filter=isRead eq false"
        "&$select=id,subject,from,body,hasAttachments,receivedDateTime"
        "&$top=50"
    )
    resp = httpx.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return list(resp.json().get("value", []))


def decode_attachments(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """Télécharge et décode les pièces jointes d'un message Graph.

    Args:
        msg: Message Graph contenant au moins ``id`` et ``hasAttachments``.

    Returns:
        Liste de dicts avec ``nom``, ``content_type``, ``content`` (bytes décodés).
    """
    import httpx

    if not msg.get("hasAttachments"):
        return []

    mailbox = os.getenv("GRAPH_MAILBOX", "")
    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}
    msg_id = msg["id"]
    url = f"{_GRAPH_BASE}/users/{mailbox}/messages/{msg_id}/attachments"
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    attachments: list[dict[str, Any]] = []
    for att in resp.json().get("value", []):
        if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue
        raw_b64 = att.get("contentBytes", "")
        content = base64.b64decode(raw_b64) if raw_b64 else b""
        attachments.append(
            {
                "nom": att.get("name", ""),
                "content_type": att.get("contentType", "application/octet-stream"),
                "content": content,
                "size": att.get("size", len(content)),
            }
        )
    return attachments


def send_mail(to: str, subject: str, body: str) -> bool:
    """Envoie un email via Graph depuis GRAPH_MAILBOX.

    Returns:
        True si envoi réussi, False sinon.
    """
    import httpx

    mailbox = os.getenv("GRAPH_MAILBOX", "")
    if not mailbox:
        logger.warning("send_mail: GRAPH_MAILBOX manquant")
        return False

    try:
        token = get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": "true",
        }
        url = f"{_GRAPH_BASE}/users/{mailbox}/sendMail"
        resp = httpx.post(url, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("send_mail: %s", exc)
        return False


def mark_read(msg_id: str) -> bool:
    """Marque un message comme lu dans GRAPH_MAILBOX.

    Returns:
        True si succès, False sinon.
    """
    import httpx

    mailbox = os.getenv("GRAPH_MAILBOX", "")
    if not mailbox:
        return False

    try:
        token = get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"{_GRAPH_BASE}/users/{mailbox}/messages/{msg_id}"
        resp = httpx.patch(url, headers=headers, json={"isRead": True}, timeout=15)
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("mark_read %s: %s", msg_id, exc)
        return False
