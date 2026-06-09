import base64
import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
TOKEN_FILE = os.path.join(BASE_DIR, os.getenv("TOKEN_FILE", "token.json"))


def _bootstrap_token_from_env() -> None:
    """Écrit token.json depuis GMAIL_TOKEN_B64 si le fichier est absent.

    Permet d'injecter le token OAuth en prod via une variable d'env Railway
    sans le committer dans le repo.
    """
    if os.path.exists(TOKEN_FILE):
        return
    token_b64 = os.getenv("GMAIL_TOKEN_B64", "")
    if not token_b64:
        return
    token_json = base64.b64decode(token_b64).decode("utf-8")
    with open(TOKEN_FILE, "w") as f:
        f.write(token_json)
    logger.info("gmail_client: token.json restauré depuis GMAIL_TOKEN_B64")


def get_gmail_service():
    _bootstrap_token_from_env()

    if not os.path.exists(CREDENTIALS_FILE):
        raise RuntimeError(
            f"Gmail OAuth non configuré : {CREDENTIALS_FILE} introuvable. "
            "En prod, injectez GMAIL_TOKEN_B64 (token seul suffit si refresh_token présent)."
        )
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    logger.info("Gmail service initialise")
    return build("gmail", "v1", credentials=creds)


def get_emails(max_results=20):
    service = get_gmail_service()
    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, labelIds=["INBOX", "UNREAD"])
        .execute()
    )
    messages = results.get("messages", [])
    logger.info(f"Gmail: {len(messages)} emails non lus")
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
