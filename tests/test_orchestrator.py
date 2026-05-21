"""Tests for orchestrator.run() — verifies sequencing and error handling."""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import apps.email_agent.orchestrator as orch

_EMAILS = [
    {
        "id": "1",
        "subject": "Test",
        "from": "a@b.com",
        "date": "2026-05-14",
        "body": "hi",
    },
]
_ANALYZED_ONE = {
    **_EMAILS[0],
    "priority": "haute",
    "category": "action_requise",
    "summary": "A faire",
    "action": "Repondre",
    "suggested_reply": None,
}
_KPIS = {
    "emails_analyses": 1,
    "temps_theorique_min": 45,
    "temps_agent_min": 2.0,
    "temps_gagne_min": 43.0,
    "gain_pourcentage": 95.6,
    "valeur_estimee_eur": 57.3,
    "semaine": "2026-W20",
}


def _run_with_mocks(
    fetch_return=None,
    analyze_side_effect=None,
    analyze_return=None,
    write_email_return=True,
    write_kpis_return=None,
    build_return="<html/>",
    send_email_return=True,
    send_telegram_return=True,
    icp_return="icp",
):
    """Helper: run orchestrator.run() with all agents mocked via patch.object."""
    fetch_return = fetch_return if fetch_return is not None else _EMAILS
    analyze_return = analyze_return if analyze_return is not None else _ANALYZED_ONE
    write_kpis_return = write_kpis_return if write_kpis_return is not None else _KPIS

    mocks: dict[str, MagicMock] = {}
    with (
        patch.object(
            orch.gmail_fetcher, "fetch_emails", return_value=fetch_return
        ) as m_fetch,
        patch.object(orch.email_analyzer, "load_icp", return_value=icp_return) as m_icp,
        patch.object(
            orch.email_analyzer,
            "analyze_email",
            **(
                {"side_effect": analyze_side_effect}
                if analyze_side_effect
                else {"return_value": analyze_return}
            ),
        ) as m_analyze,
        patch.object(
            orch.supabase_writer, "write_email", return_value=write_email_return
        ) as m_write,
        patch.object(
            orch.supabase_writer, "write_kpis", return_value=write_kpis_return
        ) as m_kpis,
        patch.object(
            orch.report_builder, "build_report", return_value=build_return
        ) as m_build,
        patch.object(
            orch.gmail_reporter, "send_email_report", return_value=send_email_return
        ) as m_email,
        patch.object(
            orch.telegram_sender, "send_telegram", return_value=send_telegram_return
        ) as m_tg,
    ):
        orch.run()
        mocks = {
            "fetch": m_fetch,
            "load_icp": m_icp,
            "analyze": m_analyze,
            "write_email": m_write,
            "write_kpis": m_kpis,
            "build": m_build,
            "send_email": m_email,
            "telegram": m_tg,
        }

    return mocks


def test_run_calls_all_agents_in_order() -> None:
    mocks = _run_with_mocks()

    mocks["fetch"].assert_called_once()
    mocks["load_icp"].assert_called_once()
    mocks["analyze"].assert_called_once()
    mocks["write_email"].assert_called_once()
    mocks["build"].assert_called_once()
    mocks["send_email"].assert_called_once()
    mocks["write_kpis"].assert_called_once()
    mocks["telegram"].assert_called_once()


def test_run_aborts_on_fetch_failure() -> None:
    mocks: dict[str, MagicMock] = {}
    with (
        patch.object(
            orch.gmail_fetcher, "fetch_emails", side_effect=RuntimeError("API down")
        ),
        patch.object(orch.email_analyzer, "load_icp", return_value="icp"),
        patch.object(
            orch.email_analyzer, "analyze_email", return_value=_ANALYZED_ONE
        ) as m_analyze,
        patch.object(orch.supabase_writer, "write_email", return_value=True),
        patch.object(orch.supabase_writer, "write_kpis", return_value=_KPIS),
        patch.object(orch.report_builder, "build_report", return_value="<html/>"),
        patch.object(orch.gmail_reporter, "send_email_report", return_value=True),
        patch.object(orch.telegram_sender, "send_telegram", return_value=True),
    ):
        orch.run()  # must not raise
        mocks["analyze"] = m_analyze

    mocks["analyze"].assert_not_called()


def test_run_aborts_when_inbox_empty() -> None:
    mocks: dict[str, MagicMock] = {}
    with (
        patch.object(orch.gmail_fetcher, "fetch_emails", return_value=[]),
        patch.object(orch.email_analyzer, "load_icp", return_value="icp"),
        patch.object(
            orch.email_analyzer, "analyze_email", return_value=_ANALYZED_ONE
        ) as m_analyze,
        patch.object(orch.supabase_writer, "write_email", return_value=True),
        patch.object(orch.supabase_writer, "write_kpis", return_value=_KPIS),
        patch.object(orch.report_builder, "build_report", return_value="<html/>"),
        patch.object(orch.gmail_reporter, "send_email_report", return_value=True),
        patch.object(orch.telegram_sender, "send_telegram", return_value=True),
    ):
        orch.run()
        mocks["analyze"] = m_analyze

    mocks["analyze"].assert_not_called()


def test_run_skips_failed_emails_but_continues() -> None:
    """An analyze failure on one email must not stop the pipeline."""
    two_emails = [_EMAILS[0], {**_EMAILS[0], "id": "2", "subject": "Second"}]
    with (
        patch.object(orch.gmail_fetcher, "fetch_emails", return_value=two_emails),
        patch.object(orch.email_analyzer, "load_icp", return_value="icp"),
        patch.object(
            orch.email_analyzer,
            "analyze_email",
            side_effect=[RuntimeError("Claude timeout"), _ANALYZED_ONE],
        ),
        patch.object(orch.supabase_writer, "write_email", return_value=True) as m_write,
        patch.object(orch.supabase_writer, "write_kpis", return_value=_KPIS),
        patch.object(
            orch.report_builder, "build_report", return_value="<html/>"
        ) as m_build,
        patch.object(orch.gmail_reporter, "send_email_report", return_value=True),
        patch.object(orch.telegram_sender, "send_telegram", return_value=True),
    ):
        orch.run()

    assert m_write.call_count == 1
    m_build.assert_called_once()


def test_run_telegram_receives_kpis() -> None:
    with (
        patch.object(orch.gmail_fetcher, "fetch_emails", return_value=_EMAILS),
        patch.object(orch.email_analyzer, "load_icp", return_value="icp"),
        patch.object(orch.email_analyzer, "analyze_email", return_value=_ANALYZED_ONE),
        patch.object(orch.supabase_writer, "write_email", return_value=True),
        patch.object(orch.supabase_writer, "write_kpis", return_value=_KPIS),
        patch.object(orch.report_builder, "build_report", return_value="<html/>"),
        patch.object(orch.gmail_reporter, "send_email_report", return_value=True),
        patch.object(orch.telegram_sender, "send_telegram", return_value=True) as m_tg,
    ):
        orch.run()

    assert m_tg.call_args[0][1] == _KPIS


def test_run_icp_loaded_once_for_multiple_emails() -> None:
    three_emails = [dict(_EMAILS[0], id=str(i)) for i in range(3)]
    with (
        patch.object(orch.gmail_fetcher, "fetch_emails", return_value=three_emails),
        patch.object(orch.email_analyzer, "load_icp", return_value="icp") as m_icp,
        patch.object(
            orch.email_analyzer, "analyze_email", return_value=_ANALYZED_ONE
        ) as m_analyze,
        patch.object(orch.supabase_writer, "write_email", return_value=True),
        patch.object(orch.supabase_writer, "write_kpis", return_value=_KPIS),
        patch.object(orch.report_builder, "build_report", return_value="<html/>"),
        patch.object(orch.gmail_reporter, "send_email_report", return_value=True),
        patch.object(orch.telegram_sender, "send_telegram", return_value=True),
    ):
        orch.run()

    m_icp.assert_called_once()
    assert m_analyze.call_count == 3
