import os

import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def analyze_email(email: dict) -> dict:
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
        messages=[{"role": "user", "content": prompt}],
    )

    import json

    try:
        result = json.loads(response.content[0].text)
    except Exception:
        result = {
            "priority": "moyenne",
            "category": "information",
            "summary": "Impossible d analyser",
            "action": None,
            "suggested_reply": None,
        }

    return {**email, **result}


def analyze_emails(emails: list) -> list:
    print(f"Analyse de {len(emails)} emails avec Claude...")
    results = []
    for i, email in enumerate(emails):
        print(f"  [{i + 1}/{len(emails)}] {email['subject'][:50]}...")
        analyzed = analyze_email(email)
        results.append(analyzed)
    return results


if __name__ == "__main__":
    from gmail_client import get_emails

    emails = get_emails(max_results=5)
    analyzed = analyze_emails(emails)
    for e in analyzed:
        print(f"\n[{e['priority'].upper()}] {e['subject']}")
        print(f"  Categorie: {e['category']}")
        print(f"  Resume: {e['summary']}")
        if e["action"]:
            print(f"  Action: {e['action']}")
