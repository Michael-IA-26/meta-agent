import logging

from apps.shared.telegram import send_telegram_message

logger = logging.getLogger(__name__)


def send_telegram_report(analyzed_emails: list, kpis: dict | None = None) -> bool:
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
    ok = send_telegram_message(msg)
    if ok:
        logger.info("Rapport Telegram envoye !")
    return ok
