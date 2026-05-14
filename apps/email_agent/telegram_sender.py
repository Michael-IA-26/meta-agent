import logging
import os

import requests  # type: ignore

logger = logging.getLogger(__name__)


def send_telegram_report(analyzed_emails: list, kpis: dict | None = None) -> bool:
    """Send a markdown summary of *analyzed_emails* (with optional KPI block) to Telegram."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        logger.error("Tokens Telegram manquants")
        return False

    haute = [e for e in analyzed_emails if e.get("priority") == "haute"]
    actions = [e for e in analyzed_emails if e.get("action")]
    inutiles = [e for e in analyzed_emails if e.get("category") == "inutile"]

    lines = []
    lines.append("*Rapport Email du jour*")
    lines.append("")
    lines.append(str(len(analyzed_emails)) + " emails analyses")
    lines.append(
        "Rouge: "
        + str(len(haute))
        + " haute | Poubelle: "
        + str(len(inutiles))
        + " inutiles"
    )

    if kpis:
        lines.append("")
        lines.append("*KPIs :*")
        lines.append("Temps gagne : " + str(kpis.get("temps_gagne_min")) + " min")
        lines.append("Gain : " + str(kpis.get("gain_pourcentage")) + "%")
        lines.append("Valeur : " + str(kpis.get("valeur_estimee_eur")) + " EUR")

    if haute:
        lines.append("")
        lines.append("*Prioritaires :*")
        for e in haute[:3]:
            lines.append("- " + e.get("subject", "")[:50])
            if e.get("action"):
                lines.append("  -> " + e.get("action", "")[:80])

    if actions:
        lines.append("")
        lines.append(str(len(actions)) + " taches identifiees")
        for i, e in enumerate(actions[:3], 1):
            lines.append(str(i) + ". " + e.get("action", "")[:80])

    lines.append("")
    lines.append("_Rapport genere par Meta-Agent_")

    msg = "\n".join(lines)

    api_url = "https://api.telegram.org/bot" + token + "/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Rapport Telegram envoye")
            return True
        else:
            logger.error("Erreur Telegram : %s", response.text)
            return False
    except Exception as e:
        logger.error("Erreur Telegram : %s", e)
        return False


if __name__ == "__main__":
    test_emails = [
        {
            "subject": "CREATION DE COMPTE VESPER",
            "from": "grace@also.com",
            "priority": "haute",
            "category": "action_requise",
            "summary": "Demande de creation de compte",
            "action": "Traiter la demande de creation de compte",
            "suggested_reply": None,
        },
        {
            "subject": "LinkedIn notification",
            "from": "linkedin@linkedin.com",
            "priority": "basse",
            "category": "inutile",
            "summary": "Notification LinkedIn",
            "action": None,
            "suggested_reply": None,
        },
    ]
    test_kpis = {
        "temps_gagne_min": 42.9,
        "gain_pourcentage": 95.3,
        "valeur_estimee_eur": 57.2,
    }
    result = send_telegram_report(test_emails, test_kpis)
    logger.info("Resultat : %s", "OK" if result else "ERREUR")
