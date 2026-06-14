"""Unified mailer — Graph-first, SMTP fallback.

Usage in agents:
    from apps.jmpartners.integrations.mailer import send_email
    send_email(to, subject, html_or_text, attachments=[("f.pdf", bytes, "application/pdf")])
"""

from __future__ import annotations

import logging
import os
from typing import Any

from apps.jmpartners.integrations.graph_mail import send_mail

__all__ = ["send_email"]

logger = logging.getLogger(__name__)


def _graph_configured() -> bool:
    return bool(
        os.environ.get("GRAPH_TENANT_ID")
        and os.environ.get("GRAPH_CLIENT_ID")
        and os.environ.get("GRAPH_CLIENT_SECRET")
    )


def _send_smtp(
    to: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """SMTP fallback (basic auth, TLS). Returns True on success."""
    import smtplib  # noqa: PLC0415
    from email.mime.application import MIMEApplication  # noqa: PLC0415
    from email.mime.multipart import MIMEMultipart  # noqa: PLC0415
    from email.mime.text import MIMEText  # noqa: PLC0415

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_password = os.environ.get("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.warning("mailer — SMTP non configuré, email non envoyé")
        return False

    try:
        msg: Any = MIMEMultipart()
        msg["From"] = smtp_user
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html" if body.lstrip().startswith("<") else "plain", "utf-8"))

        for fname, content, mime in (attachments or []):
            part = MIMEApplication(content, _subtype=mime.split("/")[-1])
            part.add_header("Content-Disposition", "attachment", filename=fname)
            msg.attach(part)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return True
    except Exception as exc:
        logger.error(f"mailer — erreur SMTP vers {to} : {exc}")
        return False


def send_email(
    to: str,
    subject: str,
    html: str,
    attachments: list[tuple[str, bytes, str]] | None = None,
) -> bool:
    """Send an email via Graph (preferred) or SMTP (fallback).

    Args:
        to: recipient address.
        subject: subject line.
        html: HTML or plain-text body.
        attachments: list of (filename, content_bytes, mimetype).

    Returns:
        True on success, False on failure (never raises).
    """
    if _graph_configured():
        try:
            send_mail(to, subject, html, attachments=attachments)
            return True
        except Exception as exc:
            logger.error(f"mailer — erreur Graph vers {to} : {exc}")
            return False
    return _send_smtp(to, subject, html, attachments)
