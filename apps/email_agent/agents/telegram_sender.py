"""Telegram sender agent — posts the daily summary to a Telegram chat."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

import telegram_sender as _tg  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailAnalyzed, KpiResult  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)


def send_telegram(
    analyzed_emails: list[EmailAnalyzed],
    kpis: KpiResult | None = None,
) -> bool:
    """Send the daily Telegram summary for *analyzed_emails* with optional KPI block.

    Returns True on success, False on failure.
    """
    success: bool = _tg.send_telegram_report(
        analyzed_emails,  # type: ignore[arg-type]
        kpis,  # type: ignore[arg-type]
    )
    if success:
        logger.info("TelegramSender: report sent")
    else:
        logger.error("TelegramSender: send failed")
    return success
