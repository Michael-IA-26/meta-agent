import json
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anthropic
from storage import save_email

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_icp(icp_name: str = "agence_conseil") -> str:
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    icp_path = os.path.join(base_dir, "packages", "prompts", "icps", f"{icp_name}.md")
    try:
        with open(icp_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def analyze_email(email: dict, icp_context: str = "") -> dict:
    icp_section = f"\n\nCONTEXTE METIER:\n{icp_context}" if icp_context else ""

    prompt = f"""Analyse cet email et reponds en JSON uniquement, sans markdown.{icp_section}

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
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        block = response.content[0]
        result = json.loads(block.text if hasattr(block, "text") else "{}")
    except Exception:
        result = {
            "priority": "moyenne",
            "category": "information",
            "summary": "Impossible d analyser",
            "action": None,
            "suggested_reply": None,
        }

    analyzed = {**email, **result}
    result_save = save_email(analyzed)
    logger.info(f"  Supabase: {'OK' if result_save else 'ERREUR'}")
    return analyzed


def analyze_emails(emails: list, icp_name: str = "agence_conseil") -> list:
    icp_context = load_icp(icp_name)
    if icp_context:
        logger.info(f"ICP charge : {icp_name}")
    logger.info(f"Analyse de {len(emails)} emails avec Claude...")
    results = []
    for i, email in enumerate(emails):
        logger.info(f"  [{i + 1}/{len(emails)}] {email['subject'][:50]}...")
        analyzed = analyze_email(email, icp_context)
        results.append(analyzed)
    return results
