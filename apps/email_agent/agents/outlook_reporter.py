"""Outlook reporter agent — envoie le rapport HTML via Microsoft Graph /sendMail."""
from __future__ import annotations

import logging
import os
import sys

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

from outlook_client import graph_post  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_RECIPIENT = "michael@myvesper.fr"


def send_email_report(html: str, subject: str, recipient: str = "") -> bool:
    """Send *html* as email via Microsoft Graph to *recipient*.

    Falls back to RAPPORT_EMAIL env var, then to the default address.
    Returns True on success, False on failure.
    """
    to = recipient or os.getenv("RAPPORT_EMAIL", _DEFAULT_RECIPIENT)
    try:
        graph_post("/me/sendMail", {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": html},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": False,
        })
        logger.info("OutlookReporter: report sent to %s", to)
        return True
    except Exception as exc:
        logger.error("OutlookReporter: send failed — %s", exc)
        return False
