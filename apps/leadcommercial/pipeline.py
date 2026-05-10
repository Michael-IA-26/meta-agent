import logging
import os

from apps.leadcommercial.scorer import score_lead
from apps.leadcommercial.sirene_client import fetch_and_parse_idf

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SCORE_THRESHOLD = int(os.getenv("LEAD_SCORE_THRESHOLD", "50"))


def format_lead_alert(company: dict, score_result: dict) -> str:
    lines = [
        "🎯 *Nouveau lead LeadCommercial*",
        "",
        f"*{company['denomination']}*",
        f"📍 {company['commune']} ({company['dept']})",
        f"🏭 NAF : {company['code_naf'] or 'N/A'}",
        f"📅 Créé le : {company['date_creation']}",
        f"🔢 SIREN : {company['siren']}",
        "",
        f"⭐ Score : *{score_result['score']}/100*",
        f"📊 Signal : {score_result['signal_type']}",
        "",
        f"_Détail scoring : {', '.join(score_result['scoring_details'])}_",
    ]
    return "\n".join(lines)


def send_telegram_alert(message: str) -> bool:
    import httpx

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning(
            "Telegram non configure — TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID manquant"
        )
        return False

    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        r.raise_for_status()
        logger.info("Alerte Telegram envoyee")
        return True
    except Exception as e:
        logger.error(f"Erreur Telegram : {e}")
        return False


def run_pipeline(date: str | None = None, dry_run: bool = False) -> list[dict]:
    logger.info("Pipeline LeadCommercial — demarrage")

    # 1. Fetch Sirene IDF
    companies = fetch_and_parse_idf(max_results=100, date=date)
    logger.info(f"Pipeline: {len(companies)} entreprises IDF recues")

    # 2. Scorer + filtrer
    qualified_leads = []
    for company in companies:
        score_result = score_lead(company, signal_type="creation")
        if score_result["score"] >= SCORE_THRESHOLD:
            lead = {**company, **score_result}
            qualified_leads.append(lead)
            logger.info(
                f"Lead qualifie : {company['denomination']} "
                f"({company['dept']}) — score {score_result['score']}"
            )

            # 3. Alerte Telegram
            message = format_lead_alert(company, score_result)
            if dry_run:
                logger.info(f"[DRY RUN] Alerte non envoyee :\n{message}")
            else:
                send_telegram_alert(message)

    logger.info(
        f"Pipeline termine : {len(qualified_leads)}/{len(companies)} leads qualifies"
    )
    return qualified_leads
