"""Supabase writer agent — persists a single analyzed email and KPI stats."""
from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

from storage import calculate_and_save_kpis  # noqa: E402
from storage import save_email as _save_email  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailAnalyzed, KpiResult  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)


def write_email(analyzed: EmailAnalyzed) -> bool:
    """Persist a single analyzed email to Supabase.

    Returns True on success, False on failure (errors are logged, not raised).
    """
    success: bool = _save_email(analyzed)  # type: ignore[arg-type]
    if success:
        logger.info(
            "SupabaseWriter: saved '%s'",
            analyzed.get("subject", "")[:50],  # type: ignore[attr-defined]
        )
    else:
        logger.error(
            "SupabaseWriter: failed to save '%s'",
            analyzed.get("subject", "")[:50],  # type: ignore[attr-defined]
        )
    return success


def write_kpis(analyzed_emails: list[EmailAnalyzed], temps_agent_sec: float) -> KpiResult:
    """Calculate KPIs and persist them to Supabase.

    Returns a KpiResult dict; returns an empty dict cast on Supabase failure.
    """
    result: dict = calculate_and_save_kpis(
        analyzed_emails,  # type: ignore[arg-type]
        temps_agent_sec,
    )
    if result:
        logger.info("SupabaseWriter: KPIs saved — %s", result)
    else:
        logger.error("SupabaseWriter: KPI save failed")
    return result  # type: ignore[return-value]
