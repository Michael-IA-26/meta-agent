from datetime import datetime


def generate_report(analyzed_emails):
    today = datetime.now().strftime("%d/%m/%Y")
    haute = [e for e in analyzed_emails if e["priority"] == "haute"]
    moyenne = [e for e in analyzed_emails if e["priority"] == "moyenne"]
    basse = [e for e in analyzed_emails if e["priority"] == "basse"]
    actions = [e for e in analyzed_emails if e.get("action")]
    reponses = [e for e in analyzed_emails if e.get("suggested_reply")]
    inutiles = [e for e in analyzed_emails if e.get("category") == "inutile"]
    r = []
    r.append(f"RAPPORT EMAIL DU {today}")
    r.append(f"RESUME: {len(analyzed_emails)} emails analyses")
    r.append(f"  Haute: {len(haute)} | Moyenne: {len(moyenne)} | Basse: {len(basse)}")
    r.append("\nEMAILS PRIORITAIRES")
    for e in haute:
        r.append(f"  * {e['subject']}")
        r.append(f"    De: {e['from']}")
        r.append(f"    Resume: {e['summary']}")
        r.append(f"    Action: {e.get('action', 'Aucune')}")
    r.append("\nTACHES A FAIRE")
    for i, e in enumerate(actions, 1):
        r.append(f"  {i}. {e.get('action')}")
    r.append("\nSUGGESTIONS DE REPONSES")
    for e in reponses:
        r.append(f"  * {e['subject']}: {e.get('suggested_reply')}")
    r.append("\nEMAILS INUTILES")
    for e in inutiles:
        r.append(f"  * {e['subject']} - {e['from']}")
    return "\n".join(r)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, ".")
    from analyzer import analyze_emails
    from gmail_client import get_emails

    emails = get_emails(max_results=5)
    analyzed = analyze_emails(emails)
    report = generate_report(analyzed)
    print(report)
