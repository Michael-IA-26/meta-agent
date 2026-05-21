"""Report builder agent — assembles the HTML email report from analyzed emails."""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

from sender import report_to_html  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailAnalyzed  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)


def build_report(analyzed_emails: list[EmailAnalyzed]) -> str:
    """Build and return the HTML report string from a list of analyzed emails.

    The returned string is a self-contained HTML document ready to be sent by email.
    """
    html: str = report_to_html(analyzed_emails)  # type: ignore[arg-type]
    logger.info(
        "ReportBuilder: HTML report built for %d emails", len(analyzed_emails)
    )
    return html
