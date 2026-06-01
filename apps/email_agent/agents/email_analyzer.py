"""Email analyzer agent — classifies a single email using Claude. No side-effects."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Any

_EMAIL_AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _EMAIL_AGENT_DIR not in sys.path:
    sys.path.insert(0, _EMAIL_AGENT_DIR)

import json  # noqa: E402

from analyzer import _build_system_prompt  # noqa: E402
from analyzer import load_icp as _load_icp  # noqa: E402
from apps.shared.claude_client import get_client  # noqa: E402

if TYPE_CHECKING:
    from agents import EmailAnalyzed, EmailRaw  # type: ignore[import]  # noqa: F401

logger = logging.getLogger(__name__)

_client = get_client("email_analyzer")


def load_icp(icp_name: str = "agence_conseil") -> str:
    """Load and return the ICP context string for the given profile name."""
    context = _load_icp(icp_name)
    if context:
        logger.info("EmailAnalyzer: ICP loaded (%s)", icp_name)
    else:
        logger.warning("EmailAnalyzer: ICP absent or empty (%s)", icp_name)
    return context


def analyze_email(email: EmailRaw, icp_context: str = "") -> EmailAnalyzed:
    """Classify a single email using Claude.

    Returns an EmailAnalyzed dict enriched with priority, category, summary,
    action, and suggested_reply. Raises on Claude API error.
    """
    system = _build_system_prompt(icp_context)
    prompt = (
        "Analyse cet email et reponds en JSON uniquement, sans markdown.\n\n"
        f"Email:\n"
        f"- De: {email['from']}\n"
        f"- Sujet: {email['subject']}\n"
        f"- Date: {email['date']}\n"
        f"- Contenu: {email['body']}\n\n"
        "Reponds avec exactement ce format JSON:\n"
        "{\n"
        '  "priority": "haute|moyenne|basse",\n'
        '  "category": "action_requise|reponse_requise|information|inutile",\n'
        '  "summary": "resume en 1 phrase",\n'
        '  "action": "action a faire ou null",\n'
        '  "suggested_reply": "suggestion de reponse ou null"\n'
        "}"
    )
    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        raw: str = getattr(response.content[0], "text", "") or ""
        classification: dict[str, Any] = json.loads(raw)
    except Exception:
        logger.warning(
            "EmailAnalyzer: JSON parse failed for '%s', using fallback",
            email.get("subject", "")[:50],
        )
        classification = {
            "priority": "moyenne",
            "category": "information",
            "summary": "Impossible d analyser",
            "action": None,
            "suggested_reply": None,
        }
    result: dict[str, Any] = {**email, **classification}
    logger.debug(
        "EmailAnalyzer: classified '%s' → %s/%s",
        email.get("subject", "")[:50],
        classification.get("priority"),
        classification.get("category"),
    )
    return result  # type: ignore[return-value]
