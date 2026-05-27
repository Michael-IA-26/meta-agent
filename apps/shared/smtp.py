"""Shared SMTP sender."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")


def send_email(to: str, subject: str, body: str, html: bool = False) -> bool:
    """Envoie un email. Retourne True si succès."""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("smtp — SMTP_USER/PASSWORD non configurés, email non envoyé")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to
        mime_type = "html" if html else "plain"
        msg.attach(MIMEText(body, mime_type, "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())
        return True
    except Exception as exc:
        logger.error("smtp — erreur envoi vers %s : %s", to, exc)
        return False
