"""Gmail API client — supports production (env/base64) and local (file) auth modes."""

import base64
import json
import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, os.getenv("TOKEN_FILE", "token.json"))
TOKEN_VESPER_FILE = os.path.join(BASE_DIR, "token_vesper.json")


def _is_production() -> bool:
    """Return True when running in a production environment (Railway)."""
    return bool(os.environ.get("GMAIL_TOKEN_B64"))


def _load_credentials_from_env(env_var: str) -> Credentials:
    """Decode a base64-encoded token from an env var and return Credentials."""
    raw = os.environ[env_var]
    token_data: dict[str, Any] = json.loads(base64.b64decode(raw).decode("utf-8"))
    return Credentials.from_authorized_user_info(token_data, SCOPES)


def _load_credentials_from_file(token_file: str) -> Credentials | None:
    """Load Credentials from a local JSON token file, or None if absent."""
    if os.path.exists(token_file):
        return Credentials.from_authorized_user_file(token_file, SCOPES)
    return None


def _get_credentials(token_file: str, env_var: str) -> Credentials:
    """Return valid Gmail Credentials, auto-detecting the auth mode.

    Production: decodes *env_var* (base64 JSON), refreshes in-memory if expired.
    Local: reads *token_file*, runs OAuth flow when missing, persists updates.
    """
    if _is_production():
        creds = _load_credentials_from_env(env_var)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    # Local mode — may need refresh or full OAuth flow
    maybe_creds = _load_credentials_from_file(token_file)
    if maybe_creds and maybe_creds.valid:
        return maybe_creds

    if maybe_creds and maybe_creds.expired and maybe_creds.refresh_token:
        maybe_creds.refresh(Request())
        fresh: Credentials = maybe_creds
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        fresh = flow.run_local_server(port=0)
    with open(token_file, "w") as fh:
        fh.write(fresh.to_json())
    return fresh


def get_gmail_service() -> Any:
    """Return an authenticated Gmail API service for the primary account."""
    return build("gmail", "v1", credentials=_get_credentials(TOKEN_FILE, "GMAIL_TOKEN_B64"))


def get_gmail_service_vesper() -> Any:
    """Return an authenticated Gmail API service for the Vesper account."""
    return build(
        "gmail", "v1", credentials=_get_credentials(TOKEN_VESPER_FILE, "GMAIL_TOKEN_VESPER_B64")
    )


def get_emails(max_results: int = 20) -> list[dict[str, Any]]:
    """Fetch unread inbox emails from the primary Gmail account."""
    service = get_gmail_service()
    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, labelIds=["INBOX", "UNREAD"])
        .execute()
    )
    messages = results.get("messages", [])
    emails = []
    for msg in messages:
        detail = (
            service.users()
            .messages()
            .get(userId="me", id=msg["id"], format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        body = ""
        if "parts" in detail["payload"]:
            for part in detail["payload"]["parts"]:
                if part["mimeType"] == "text/plain":
                    data = part["body"].get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode(
                            "utf-8", errors="ignore"
                        )
                        break
        elif "body" in detail["payload"]:
            data = detail["payload"]["body"].get("data", "")
            if data:
                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        emails.append(
            {
                "id": msg["id"],
                "subject": headers.get("Subject", "Sans objet"),
                "from": headers.get("From", "Inconnu"),
                "date": headers.get("Date", ""),
                "body": body[:500],
            }
        )
    return emails
