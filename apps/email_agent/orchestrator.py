"""Orchestrator — sequences the email-agent pipeline, no business logic."""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

from agents import EmailAnalyzed  # noqa: E402
import agents.email_analyzer as email_analyzer  # noqa: E402
import agents.gmail_fetcher as gmail_fetcher  # noqa: E402
import agents.gmail_reporter as gmail_reporter  # noqa: E402
import agents.report_builder as report_builder  # noqa: E402
import agents.supabase_writer as supabase_writer  # noqa: E402
import agents.telegram_sender as telegram_sender  # noqa: E402

logger = logging.getLogger(__name__)


def run(max_results: int = 20, icp_name: str = "agence_conseil") -> None:
    """Run the full email-agent pipeline once.

    Steps:
    1. Fetch unread emails (GmailFetcher)
    2. Load ICP context (EmailAnalyzer)
    3. Analyze each email + write to Supabase (EmailAnalyzer + SupabaseWriter)
    4. Build HTML report (ReportBuilder)
    5. Send report by email (GmailReporter)
    6. Persist KPIs (SupabaseWriter)
    7. Send Telegram summary (TelegramSender)
    """
    start = time.time()
    logger.info("Orchestrator: pipeline started")

    # 1. Fetch emails
    try:
        emails = gmail_fetcher.fetch_emails(max_results=max_results)
    except Exception as exc:
        logger.error("Orchestrator: GmailFetcher failed — %s", exc)
        return

    if not emails:
        logger.info("Orchestrator: no unread emails, pipeline aborted")
        return

    # 2. Load ICP context once for all analyses
    icp_context = email_analyzer.load_icp(icp_name)

    # 3. Analyze each email and persist individually
    analyzed: list[EmailAnalyzed] = []
    for email in emails:
        try:
            result = email_analyzer.analyze_email(email, icp_context)
        except Exception as exc:
            logger.error(
                "Orchestrator: EmailAnalyzer failed for '%s' — %s",
                email.get("subject", "")[:50],
                exc,
            )
            continue
        supabase_writer.write_email(result)
        analyzed.append(result)

    if not analyzed:
        logger.error("Orchestrator: no emails were analyzed successfully")
        return

    elapsed = time.time() - start

    # 4. Build HTML report
    try:
        html = report_builder.build_report(analyzed)
    except Exception as exc:
        logger.error("Orchestrator: ReportBuilder failed — %s", exc)
        html = ""

    # 5. Send report by email
    if html:
        today = datetime.now().strftime("%d/%m/%Y")
        gmail_reporter.send_email_report(html, subject=f"Votre rapport du jour - {today}")

    # 6. Persist KPIs
    kpis = supabase_writer.write_kpis(analyzed, temps_agent_sec=elapsed)

    # 7. Telegram summary
    telegram_sender.send_telegram(analyzed, kpis or None)

    logger.info(
        "Orchestrator: pipeline done in %.1fs — %d/%d emails analyzed",
        elapsed,
        len(analyzed),
        len(emails),
    )
