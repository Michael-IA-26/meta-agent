"""Microsoft Graph mail integration — OAuth2 app-only (client credentials)."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any

import httpx
import msal

__all__ = ["get_token", "fetch_unread", "decode_attachments", "mark_read"]

logger = logging.getLogger(__name__)

GRAPH_MAILBOX = os.getenv("GRAPH_MAILBOX", "")
_GRAPH_BASE = "https://graph.microsoft.com/v1.0"
_SCOPE = ["https://graph.microsoft.com/.default"]


def get_token() -> str:
    """Acquire an app-only access token via MSAL ConfidentialClientApplication."""
    tenant_id = os.environ.get("GRAPH_TENANT_ID", "")
    client_id = os.environ.get("GRAPH_CLIENT_ID", "")
    client_secret = os.environ.get("GRAPH_CLIENT_SECRET", "")
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    result = app.acquire_token_for_client(scopes=_SCOPE)
    if "access_token" not in result:
        raise RuntimeError(f"MSAL token error: {result.get('error_description', result)}")
    return result["access_token"]  # type: ignore[return-value]


def fetch_unread(mailbox: str = "") -> list[dict[str, Any]]:
    """Return up to 25 unread messages with attachments from the inbox.

    Each item is the raw Graph message object (value element).
    """
    box = mailbox or os.environ.get("GRAPH_MAILBOX", "")
    if not box:
        raise ValueError("GRAPH_MAILBOX is not set")
    token = get_token()
    url = (
        f"{_GRAPH_BASE}/users/{box}/mailFolders/Inbox/messages"
        "?$filter=isRead eq false&$expand=attachments&$top=25"
    )
    resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("value", [])


def decode_attachments(message: dict[str, Any]) -> list[tuple[str, bytes]]:
    """Extract (filename, raw_bytes) for every fileAttachment on a message."""
    results: list[tuple[str, bytes]] = []
    for att in message.get("attachments", []):
        if att.get("@odata.type") != "#microsoft.graph.fileAttachment":
            continue
        content = att.get("contentBytes", "")
        if content:
            results.append((att.get("name", "attachment"), base64.b64decode(content)))
    return results


def mark_read(message_id: str, mailbox: str = "") -> None:
    """PATCH a message to mark it as read."""
    box = mailbox or os.environ.get("GRAPH_MAILBOX", "")
    if not box:
        raise ValueError("GRAPH_MAILBOX is not set")
    token = get_token()
    url = f"{_GRAPH_BASE}/users/{box}/messages/{message_id}"
    resp = httpx.patch(
        url,
        json={"isRead": True},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
