"""Microsoft Graph API client — MSAL refresh token, no browser needed."""
from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx
import msal

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "offline_access",
]


def _get_access_token() -> str:
    """Return a fresh access token using the stored refresh token.

    Requires env vars: OUTLOOK_CLIENT_ID, OUTLOOK_CLIENT_SECRET,
    OUTLOOK_TENANT_ID, OUTLOOK_REFRESH_TOKEN.
    Raises RuntimeError with a clear message on auth failure.
    """
    app = msal.ConfidentialClientApplication(
        client_id=os.environ["OUTLOOK_CLIENT_ID"],
        client_credential=os.environ["OUTLOOK_CLIENT_SECRET"],
        authority=f"https://login.microsoftonline.com/{os.environ['OUTLOOK_TENANT_ID']}",
    )
    result = app.acquire_token_by_refresh_token(
        os.environ["OUTLOOK_REFRESH_TOKEN"],
        scopes=SCOPES,
    )
    if "access_token" not in result:
        raise RuntimeError(
            f"Outlook auth failed: {result.get('error_description', result.get('error', 'unknown'))}"
        )
    return result["access_token"]


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_get_access_token()}", "Accept": "application/json"}


def graph_get(path: str, **params: Any) -> dict[str, Any]:
    resp = httpx.get(f"{GRAPH_BASE}{path}", headers=_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def graph_post(path: str, payload: dict[str, Any]) -> None:
    headers = {**_headers(), "Content-Type": "application/json"}
    resp = httpx.post(f"{GRAPH_BASE}{path}", headers=headers, json=payload, timeout=30)
    resp.raise_for_status()


def get_emails(max_results: int = 20) -> list[dict[str, Any]]:
    """Fetch unread inbox emails via Microsoft Graph."""
    data = graph_get(
        "/me/mailFolders/inbox/messages",
        **{
            "$filter": "isRead eq false",
            "$top": max_results,
            "$select": "id,subject,from,receivedDateTime,body",
        },
    )
    emails = []
    for msg in data.get("value", []):
        raw_body = msg.get("body", {}).get("content", "")
        plain = re.sub(r"<[^>]+>", " ", raw_body).strip()[:500]
        emails.append({
            "id": msg["id"],
            "subject": msg.get("subject") or "Sans objet",
            "from": msg.get("from", {}).get("emailAddress", {}).get("address", "Inconnu"),
            "date": msg.get("receivedDateTime", ""),
            "body": plain,
        })
    logger.info("OutlookClient: %d unread emails fetched", len(emails))
    return emails
