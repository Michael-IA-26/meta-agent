"""Utilitaire SMTP partagé entre tous les agents."""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

__all__ = ["send_email"]

logger = logging.getLogger(__name__)


def send_email(destinataire: str, sujet: str, corps: str) -> bool:
    """Envoie un email via SMTP TLS.

    Si destinataire est vide, envoie à SMTP_USER (auto-notification cabinet).
    Returns False si SMTP non configuré ou en cas d'erreur.
    """
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    to = destinataire if destinataire else user
    if not user or not password:
        logger.warning("SMTP non configuré — email non envoyé")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = user
        msg["To"] = to
        msg["Subject"] = sujet
        msg.attach(MIMEText(corps, "plain", "utf-8"))
        host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        port = int(os.getenv("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, [to], msg.as_string())
        return True
    except Exception as exc:
        logger.error("SMTP send error to %s: %s", to, exc)
        return False
