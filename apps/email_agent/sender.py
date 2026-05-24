import base64
import logging
import os
import sys
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)
from gmail_client import get_gmail_service  # noqa: E402
from storage import calculate_and_save_kpis  # noqa: E402
from telegram_sender import send_telegram_report  # noqa: E402


def report_to_html(analyzed_emails):
    today = datetime.now().strftime("%d/%m/%Y")
    haute = [e for e in analyzed_emails if e["priority"] == "haute"]
    moyenne = [e for e in analyzed_emails if e["priority"] == "moyenne"]
    basse = [e for e in analyzed_emails if e["priority"] == "basse"]
    actions = [e for e in analyzed_emails if e.get("action")]
    reponses = [e for e in analyzed_emails if e.get("suggested_reply")]
    inutiles = [e for e in analyzed_emails if e.get("category") == "inutile"]

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:auto;padding:20px;">
<h1 style="color:#1a73e8;border-bottom:2px solid #1a73e8;padding-bottom:8px;">
Rapport Email du {today}</h1>
<p><b>{len(analyzed_emails)}</b> emails non lus analyses —
<span style="color:red">🔴 {len(haute)} haute</span> |
<span style="color:orange">🟡 {len(moyenne)} moyenne</span> |
<span style="color:green">🟢 {len(basse)} basse</span></p>
<h2 style="color:#1a73e8;text-decoration:underline;">🔴 Emails Prioritaires</h2><ul>"""

    for e in haute:
        html += f"""<li><b>{e["subject"]}</b><br>
<span style="color:gray;font-size:0.85em;font-style:italic;">
De : {e["from"]}<br>{e["summary"]}</span><br>
<span style="color:#d93025;">➡ {e.get("action", "")}</span></li><br>"""

    html += """</ul><h2 style="color:#1a73e8;text-decoration:underline;">Taches a faire</h2><ol>"""

    for e in actions:
        html += f"""<li>{e.get("action")}<br>
<span style="color:gray;font-size:0.85em;font-style:italic;">({e["subject"]})</span></li>"""

    html += """</ol><h2 style="color:#1a73e8;text-decoration:underline;">Suggestions de reponses</h2><ul>"""

    for e in reponses:
        html += f"""<li><b>{e["subject"]}</b><br>
<span style="color:gray;font-size:0.85em;font-style:italic;">{e.get("suggested_reply")}</span></li><br>"""

    html += """</ul><h2 style="color:#1a73e8;text-decoration:underline;">Emails inutiles</h2><ul>"""

    for e in inutiles:
        html += f"""<li><span style="color:gray;font-size:0.85em;font-style:italic;">
{e["subject"]} — {e["from"]}</span></li>"""

    html += """</ul><hr><p style="color:gray;font-size:0.8em;font-style:italic;">
Rapport genere automatiquement par Meta-Agent</p></body></html>"""
    return html


def send_report(analyzed_emails, temps_agent_sec=0):
    service = get_gmail_service()
    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"Votre rapport du jour - {today}"
    recipient = os.getenv("EMAIL_DEFAULT_RECIPIENT") or os.getenv("RAPPORT_EMAIL", "")
    if not recipient:
        logger.warning("send_report: EMAIL_DEFAULT_RECIPIENT non défini, rapport non envoyé")
        return False
    html_content = report_to_html(analyzed_emails)
    message = MIMEMultipart("alternative")
    message["to"] = recipient
    message["subject"] = subject
    message.attach(MIMEText(html_content, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    logger.info(f"Rapport HTML envoye a {recipient} !")

    kpis = calculate_and_save_kpis(analyzed_emails, temps_agent_sec)
    if kpis:
        logger.info(
            f"KPIs — analyses: {kpis.get('emails_analyses')} | gagne: {kpis.get('temps_gagne_min')}min | valeur: {kpis.get('valeur_estimee_eur')}EUR"
        )

    send_telegram_report(analyzed_emails, kpis)


if __name__ == "__main__":
    from analyzer import analyze_emails
    from gmail_client import get_emails

    start = time.time()
    emails = get_emails(max_results=20)
    analyzed = analyze_emails(emails)
    elapsed = time.time() - start

    send_report(analyzed, temps_agent_sec=elapsed)
