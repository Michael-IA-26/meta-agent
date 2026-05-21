"""Gmail reporter agent — sends the HTML report via Gmail."""
from __future__ import annotations

import base64
import logging
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

from gmail_client import get_gmail_service  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_RECIPIENT = "michael@myvesper.fr"


def send_email_report(html: str, subject: str, recipient: str = "") -> bool:
    """Send *html* as an email via Gmail to *recipient*.

    Falls back to the RAPPORT_EMAIL env var, then to the default address.
    Returns True on success, False on failure.
    """
    to = recipient or os.getenv("RAPPORT_EMAIL", _DEFAULT_RECIPIENT)
    try:
        service = get_gmail_service()
        message = MIMEMultipart("alternative")
        message["to"] = to
        message["subject"] = subject
        message.attach(MIMEText(html, "html", "utf-8"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        logger.info("GmailReporter: report sent to %s", to)
        return True
    except Exception as exc:
        logger.error("GmailReporter: send failed — %s", exc)
        return False
