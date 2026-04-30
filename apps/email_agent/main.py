import os
import sys
import time

import schedule
import sentry_sdk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import analyze_emails  # noqa: E402
from gmail_client import get_emails  # noqa: E402
from sender import send_report  # noqa: E402

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    environment=os.getenv("DOPPLER_ENVIRONMENT", "dev"),
    traces_sample_rate=0.1,
)


def run_daily_report():
    print("Lancement du rapport quotidien...")
    try:
        start = time.time()
        emails = get_emails(max_results=20)
        analyzed = analyze_emails(emails)
        elapsed = time.time() - start
        send_report(analyzed, temps_agent_sec=elapsed)
        print("Rapport envoye avec succes !")
    except Exception as e:
        sentry_sdk.capture_exception(e)
        print(f"Erreur capturee par Sentry : {e}")


if __name__ == "__main__":
    print("Agent email demarre - rapport envoye chaque jour a 08h45")
    print(f"Sentry initialise : {bool(os.getenv('SENTRY_DSN'))}")
    schedule.every().day.at("08:45").do(run_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)
