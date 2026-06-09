import logging
import os
import time

import schedule
import sentry_sdk

from apps.email_agent.analyzer import analyze_emails
from apps.email_agent.gmail_client import get_emails
from apps.email_agent.sender import send_report

logger = logging.getLogger(__name__)

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("DOPPLER_ENVIRONMENT", "dev"),
    traces_sample_rate=0.1,
)


def run_daily_report():
    logger.info("Lancement du rapport quotidien...")
    try:
        start = time.time()
        emails = get_emails(max_results=20)
        analyzed = analyze_emails(emails)
        elapsed = time.time() - start
        send_report(analyzed, temps_agent_sec=elapsed)
        logger.info("Rapport envoye avec succes !")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        logger.error(f"Erreur capturee par Sentry : {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("Agent email demarre - rapport envoye chaque jour a 08h45")
    logger.info(f"Sentry initialise : {bool(os.getenv('SENTRY_DSN'))}")
    schedule.every().day.at("08:45").do(run_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)
