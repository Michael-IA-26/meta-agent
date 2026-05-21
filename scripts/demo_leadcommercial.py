"""
Demo LeadCommercial — pipeline complet sur 10 entreprises IDF.

Usage:
    uv run python scripts/demo_leadcommercial.py            # envoi réel
    uv run python scripts/demo_leadcommercial.py --dry-run  # pas d'envoi
"""

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.leadcommercial.scorer import score_lead
from apps.leadcommercial.sirene_client import fetch_and_parse_idf

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPORT_PATH = (
    Path(__file__).parent.parent / "docs" / "demo" / "rapport_demo_leadcommercial.html"
)
DEMO_EMAIL = "michael@myvesper.fr"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


def _score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 50:
        return "#d97706"
    return "#dc2626"


def generate_html_report(leads: list[dict], run_at: str) -> str:
    qualified = [lead for lead in leads if lead["qualified"]]
    rows = ""
    for i, lead in enumerate(leads, 1):
        color = _score_color(lead["score"])
        badge = "✅" if lead["qualified"] else "❌"
        details = ", ".join(lead.get("scoring_details", []))
        rows += f"""
        <tr style="background:{"#f0fdf4" if lead["qualified"] else "#fff"}">
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-weight:600">{i}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{lead.get("denomination", "N/A")}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{lead.get("siren", "")}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{lead.get("dept", "")}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{lead.get("commune") or ""}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb">{lead.get("code_naf", "")}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center">
                <span style="background:{color};color:white;padding:3px 10px;border-radius:12px;font-weight:700">
                    {lead["score"]}
                </span>
            </td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;text-align:center">{badge}</td>
            <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:0.8em;color:#6b7280">{details}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Demo LeadCommercial — JM Partners</title>
<style>
  body {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f8fafc;color:#1e293b}}
  .header {{background:linear-gradient(135deg,#1e40af,#3b82f6);color:white;padding:40px;text-align:center}}
  .header h1 {{margin:0;font-size:2em}}
  .header p {{margin:8px 0 0;opacity:0.85}}
  .kpis {{display:flex;gap:20px;padding:30px;justify-content:center;flex-wrap:wrap}}
  .kpi {{background:white;border-radius:12px;padding:20px 30px;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.1);min-width:120px}}
  .kpi .value {{font-size:2.5em;font-weight:800;color:#1e40af}}
  .kpi .label {{font-size:0.85em;color:#64748b;margin-top:4px}}
  .section {{padding:0 30px 30px}}
  h2 {{color:#1e40af;margin-bottom:12px}}
  table {{width:100%;border-collapse:collapse;background:white;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  th {{background:#1e40af;color:white;padding:12px 8px;text-align:left;font-size:0.85em}}
  tr:hover {{background:#f1f5f9!important}}
  .footer {{text-align:center;padding:20px;color:#94a3b8;font-size:0.8em}}
</style>
</head>
<body>
<div class="header">
  <h1>LeadCommercial — Demo IDF</h1>
  <p>Pipeline complet · {run_at} · 10 entreprises analysées</p>
</div>

<div class="kpis">
  <div class="kpi"><div class="value">{len(leads)}</div><div class="label">Entreprises<br>analysées</div></div>
  <div class="kpi"><div class="value" style="color:#16a34a">{len(qualified)}</div><div class="label">Leads<br>qualifiés</div></div>
  <div class="kpi"><div class="value">{int(len(qualified) / len(leads) * 100) if leads else 0}%</div><div class="label">Taux de<br>qualification</div></div>
  <div class="kpi"><div class="value">{max((lead["score"] for lead in leads), default=0)}</div><div class="label">Meilleur<br>score</div></div>
</div>

<div class="section">
  <h2>Résultats détaillés</h2>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Raison sociale</th><th>SIREN</th><th>Dept</th>
        <th>Commune</th><th>NAF</th><th>Score</th><th>Qualifié</th><th>Détail scoring</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>

<div class="footer">
  Rapport généré automatiquement par Meta-Agent · JM Partners · {run_at}
</div>
</body>
</html>"""


def send_email(html: str, dry_run: bool = False) -> bool:
    if dry_run:
        logger.info("[DRY RUN] Email non envoyé vers %s", DEMO_EMAIL)
        return True
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP non configuré — email ignoré")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Demo LeadCommercial — {datetime.now().strftime('%d/%m/%Y')}"
        msg["From"] = SMTP_USER
        msg["To"] = DEMO_EMAIL
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, [DEMO_EMAIL], msg.as_string())
        logger.info("Email envoyé vers %s", DEMO_EMAIL)
        return True
    except Exception as e:
        logger.error("Erreur email : %s", e)
        return False


def send_telegram(leads: list[dict], dry_run: bool = False) -> bool:
    qualified = [lead for lead in leads if lead["qualified"]]
    lines = [
        "🚀 *Demo LeadCommercial — JM Partners*",
        "",
        f"📊 *{len(leads)}* entreprises analysées",
        f"✅ *{len(qualified)}* leads qualifiés ({int(len(qualified) / len(leads) * 100) if leads else 0}%)",
        "",
    ]
    for lead in qualified[:5]:
        lines.append(
            f"• *{lead.get('denomination', '?')}* ({lead.get('dept', '')}) — score *{lead['score']}*"
        )
    if len(qualified) > 5:
        lines.append(f"_… et {len(qualified) - 5} autres_")
    lines += ["", "📎 Rapport HTML généré dans docs/demo/"]
    message = "\n".join(lines)

    if dry_run:
        logger.info("[DRY RUN] Telegram non envoyé :\n%s", message)
        return True
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram non configuré")
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
        logger.info("Telegram envoyé")
        return True
    except Exception as e:
        logger.error("Erreur Telegram : %s", e)
        return False


MOCK_COMPANIES = [
    {
        "siren": "900000001",
        "siret": "90000000100011",
        "denomination": "LE ZINC PARISIEN SAS",
        "forme_juridique": "5710",
        "code_naf": "56.10A",
        "dept": "75",
        "commune": "PARIS 11",
        "date_creation": "2026-05-20",
    },
    {
        "siren": "900000002",
        "siret": "90000000200011",
        "denomination": "DIGITAL CONSEIL SASU",
        "forme_juridique": "5720",
        "code_naf": "70.22Z",
        "dept": "92",
        "commune": "BOULOGNE-BILLANCOURT",
        "date_creation": "2026-05-20",
    },
    {
        "siren": "900000003",
        "siret": "90000000300011",
        "denomination": "BATI PRO IDF EURL",
        "forme_juridique": "5499",
        "code_naf": "43.21A",
        "dept": "93",
        "commune": "SAINT-DENIS",
        "date_creation": "2026-05-19",
    },
    {
        "siren": "900000004",
        "siret": "90000000400011",
        "denomination": "RAMEN TOKYO PARIS",
        "forme_juridique": "5710",
        "code_naf": "56.10B",
        "dept": "75",
        "commune": "PARIS 9",
        "date_creation": "2026-05-20",
    },
    {
        "siren": "900000005",
        "siret": "90000000500011",
        "denomination": "WELLNESS YOGA 78",
        "forme_juridique": "5710",
        "code_naf": "93.13Z",
        "dept": "78",
        "commune": "VERSAILLES",
        "date_creation": "2026-05-18",
    },
    {
        "siren": "900000006",
        "siret": "90000000600011",
        "denomination": "TRAITEUR DU SUD SAS",
        "forme_juridique": "5710",
        "code_naf": "56.21Z",
        "dept": "91",
        "commune": "ÉVRY",
        "date_creation": "2026-05-20",
    },
    {
        "siren": "900000007",
        "siret": "90000000700011",
        "denomination": "IMMO INVEST 94 SASU",
        "forme_juridique": "5720",
        "code_naf": "68.20A",
        "dept": "94",
        "commune": "CRÉTEIL",
        "date_creation": "2026-05-19",
    },
    {
        "siren": "900000008",
        "siret": "90000000800011",
        "denomination": "CLEANTECH SOLUTIONS",
        "forme_juridique": "5710",
        "code_naf": "38.21Z",
        "dept": "95",
        "commune": "CERGY",
        "date_creation": "2026-05-17",
    },
    {
        "siren": "900000009",
        "siret": "90000000900011",
        "denomination": "MODE & STYLE PARIS",
        "forme_juridique": "1000",
        "code_naf": "47.71Z",
        "dept": "75",
        "commune": "PARIS 8",
        "date_creation": "2026-05-20",
    },
    {
        "siren": "900000010",
        "siret": "90000001000011",
        "denomination": "CAFÉ DES ARTISTES 77",
        "forme_juridique": "5710",
        "code_naf": "56.30Z",
        "dept": "77",
        "commune": "MEAUX",
        "date_creation": "2026-05-19",
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Demo LeadCommercial")
    parser.add_argument("--dry-run", action="store_true", help="Pas d'envoi réel")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Utilise des données de démo (sans API Sirene)",
    )
    args = parser.parse_args()

    run_at = datetime.now().strftime("%d/%m/%Y à %H:%M")
    logger.info("=== Demo LeadCommercial — %s ===", run_at)

    if args.mock:
        logger.info("Mode mock — 10 entreprises IDF de démonstration")
        companies = MOCK_COMPANIES
    else:
        logger.info("Récupération de 10 entreprises IDF via API INSEE Sirene...")
        companies = fetch_and_parse_idf(max_results=10)
    logger.info("%d entreprises IDF récupérées", len(companies))

    leads = []
    for company in companies:
        result = score_lead(company, signal_type="creation")
        leads.append({**company, **result})
        status = "QUALIFIÉ" if result["qualified"] else "rejeté"
        logger.info(
            "  %s (%s) — score %d — %s",
            company.get("denomination", "?"),
            company.get("dept", ""),
            result["score"],
            status,
        )

    html = generate_html_report(leads, run_at)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    logger.info("Rapport HTML généré : %s", REPORT_PATH)

    send_email(html, dry_run=args.dry_run)
    send_telegram(leads, dry_run=args.dry_run)

    qualified = [lead for lead in leads if lead["qualified"]]
    logger.info("=== Terminé : %d/%d leads qualifiés ===", len(qualified), len(leads))


if __name__ == "__main__":
    main()
