"""Gmail fetcher agent — returns raw unread emails from the primary account."""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Any

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

from gmail_client import get_emails  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailRaw  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)


def fetch_emails(max_results: int = 20) -> list[EmailRaw]:
    """Fetch unread inbox emails from the primary Gmail account.

    Returns a list of EmailRaw-shaped dicts.
    Raises on Gmail API failure; returns an empty list when the inbox has no unread mail.
    """
    logger.info("GmailFetcher: fetching up to %d emails", max_results)
    emails: list[Any] = get_emails(max_results=max_results)
    logger.info("GmailFetcher: fetched %d emails", len(emails))
    return emails  # type: ignore[return-value]
