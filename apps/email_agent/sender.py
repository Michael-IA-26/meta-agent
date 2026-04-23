import base64
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from gmail_client import get_gmail_service


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

    html += """</ul><h2 style="color:#1a73e8;text-decoration:underline;">✅ Taches a faire</h2><ol>"""

    for e in actions:
        html += f"""<li>{e.get("action")}<br>
<span style="color:gray;font-size:0.85em;font-style:italic;">({e["subject"]})</span></li>"""

    html += """</ol><h2 style="color:#1a73e8;text-decoration:underline;">💬 Suggestions de reponses</h2><ul>"""

    for e in reponses:
        html += f"""<li><b>{e["subject"]}</b><br>
<span style="color:gray;font-size:0.85em;font-style:italic;">{e.get("suggested_reply")}</span></li><br>"""

    html += """</ul><h2 style="color:#1a73e8;text-decoration:underline;">🗑 Emails inutiles</h2><ul>"""

    for e in inutiles:
        html += f"""<li><span style="color:gray;font-size:0.85em;font-style:italic;">
{e["subject"]} — {e["from"]}</span></li>"""

    html += """</ul><hr><p style="color:gray;font-size:0.8em;font-style:italic;">
Rapport genere automatiquement par Meta-Agent</p></body></html>"""
    return html


def send_report(analyzed_emails):
    service = get_gmail_service()
    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"Votre rapport du jour - {today}"
    recipient = "michael@myvesper.fr"
    html_content = report_to_html(analyzed_emails)
    message = MIMEMultipart("alternative")
    message["to"] = recipient
    message["subject"] = subject
    message.attach(MIMEText(html_content, "html", "utf-8"))
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Rapport HTML envoye a {recipient} !")


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from analyzer import analyze_emails
    from gmail_client import get_emails

    emails = get_emails(max_results=20)
    analyzed = analyze_emails(emails)
    send_report(analyzed)
# noqa: E501
