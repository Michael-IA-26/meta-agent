import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anthropic
from anthropic.types import TextBlock
from storage import save_email

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
logger = logging.getLogger(__name__)

SYSTEM_BASE = (
    "Tu es un assistant expert en classification d'emails professionnels. "
    "Reponds uniquement en JSON valide, sans balises markdown."
)


def load_icp(icp_name: str = "agence_conseil") -> str:
    """Load ICP markdown context from packages/prompts/icps/."""
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    icp_path = os.path.join(base_dir, "packages", "prompts", "icps", f"{icp_name}.md")
    try:
        with open(icp_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"ICP introuvable : {icp_path}")
        return ""


def _build_system_prompt(icp_context: str) -> str:
    """Assemble system prompt, injecting ICP context when available."""
    if icp_context:
        return f"{SYSTEM_BASE}\n\n{icp_context}"
    return SYSTEM_BASE


def analyze_email(email: dict, icp_context: str = "") -> dict:
    """Analyze a single email and classify it; ICP is passed as Claude system prompt."""
    system = _build_system_prompt(icp_context)

    prompt = f"""Analyse cet email et reponds en JSON uniquement, sans markdown.

Email:
- De: {email["from"]}
- Sujet: {email["subject"]}
- Date: {email["date"]}
- Contenu: {email["body"]}

Reponds avec exactement ce format JSON:
{{
  "priority": "haute|moyenne|basse",
  "category": "action_requise|reponse_requise|information|inutile",
  "summary": "resume en 1 phrase",
  "action": "action a faire ou null",
  "suggested_reply": "suggestion de reponse ou null"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        block = response.content[0]
        raw = block.text if isinstance(block, TextBlock) else ""
        result = json.loads(raw)
    except Exception:
        result = {
            "priority": "moyenne",
            "category": "information",
            "summary": "Impossible d analyser",
            "action": None,
            "suggested_reply": None,
        }

    analyzed = {**email, **result}
    if save_email(analyzed):
        logger.info(f"Email analyse et sauvegarde : {email['subject'][:50]}")
    else:
        logger.error(f"Echec sauvegarde Supabase pour : {email['subject'][:50]}")
    return analyzed


def analyze_emails(emails: list, icp_name: str = "agence_conseil") -> list:
    """Batch-analyze emails with the named ICP injected as Claude system prompt."""
    icp_context = load_icp(icp_name)
    if icp_context:
        logger.info(f"ICP charge : {icp_name}")
    else:
        logger.warning(
            f"ICP absent ou vide — analyse sans contexte metier : {icp_name}"
        )
    logger.info(f"Analyse de {len(emails)} emails avec Claude")
    results = []
    for i, email in enumerate(emails):
        logger.debug(f"[{i + 1}/{len(emails)}] {email['subject'][:50]}...")
        analyzed = analyze_email(email, icp_context)
        results.append(analyzed)
    return results
