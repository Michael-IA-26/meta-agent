import os
import sys
import time

import schedule

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer import analyze_emails
from gmail_client import get_emails
from sender import send_report


def run_daily_report():
    print("Lancement du rapport quotidien...")
    emails = get_emails(max_results=20)
    analyzed = analyze_emails(emails)
    send_report(analyzed)
    print("Rapport envoye !")


if __name__ == "__main__":
    print("Agent email demarre - rapport envoye chaque jour a 08h45")
    schedule.every().day.at("08:45").do(run_daily_report)
    while True:
        schedule.run_pending()
        time.sleep(60)
