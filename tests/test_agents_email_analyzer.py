"""Tests for agents/email_analyzer."""
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from apps.email_agent.agents.email_analyzer import analyze_email, load_icp

_MOD = "apps.email_agent.agents.email_analyzer"

_FAKE_EMAIL = {
    "id": "1",
    "subject": "Demande de devis",
    "from": "client@example.com",
    "date": "2026-05-14",
    "body": "Bonjour, nous souhaitons un devis.",
}

_CLAUDE_RESPONSE = (
    '{"priority":"haute","category":"action_requise",'
    '"summary":"Devis demande","action":"Envoyer devis","suggested_reply":null}'
)


def _make_claude_mock(text: str) -> MagicMock:
    block = MagicMock()
    block.text = text
    resp = MagicMock()
    resp.content = [block]
    return resp


def test_analyze_email_returns_enriched_dict() -> None:
    with patch(f"{_MOD}._client") as mock_client:
        mock_client.messages.create.return_value = _make_claude_mock(_CLAUDE_RESPONSE)
        result = analyze_email(_FAKE_EMAIL, icp_context="")

    assert result["priority"] == "haute"
    assert result["category"] == "action_requise"
    assert result["subject"] == _FAKE_EMAIL["subject"]


def test_analyze_email_icp_injected_as_system() -> None:
    icp = "## BASSE\nNewsletter → inutile"
    with patch(f"{_MOD}._client") as mock_client:
        mock_client.messages.create.return_value = _make_claude_mock(_CLAUDE_RESPONSE)
        analyze_email(_FAKE_EMAIL, icp_context=icp)

    kwargs = mock_client.messages.create.call_args.kwargs
    assert "system" in kwargs
    assert icp in kwargs["system"]
    assert icp not in kwargs["messages"][0]["content"]


def test_analyze_email_fallback_on_bad_json() -> None:
    with patch(f"{_MOD}._client") as mock_client:
        mock_client.messages.create.return_value = _make_claude_mock("not-json-at-all")
        result = analyze_email(_FAKE_EMAIL, icp_context="")

    assert result["priority"] == "moyenne"
    assert result["category"] == "information"


def test_analyze_email_no_supabase_call() -> None:
    """Analyzer agent must not call save_email."""
    with patch(f"{_MOD}._client") as mock_client, \
         patch(f"{_MOD}.supabase_writer", create=True) as mock_sw:
        mock_client.messages.create.return_value = _make_claude_mock(_CLAUDE_RESPONSE)
        analyze_email(_FAKE_EMAIL, icp_context="")

    # supabase_writer should never be touched by the analyzer
    mock_sw.write_email.assert_not_called() if hasattr(mock_sw, "write_email") else None


def test_load_icp_delegates_to_analyzer_load_icp() -> None:
    with patch(f"{_MOD}._load_icp", return_value="icp content") as mock_load:
        result = load_icp("agence_conseil")
    mock_load.assert_called_once_with("agence_conseil")
    assert result == "icp content"


def test_load_icp_empty_on_missing_file() -> None:
    with patch(f"{_MOD}._load_icp", return_value=""):
        result = load_icp("inexistant")
    assert result == ""
