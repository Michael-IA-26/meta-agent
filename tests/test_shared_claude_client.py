"""Tests pour apps/shared/claude_client.py — wrapper Anthropic + suivi token_usage."""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

_MOD = "apps.shared.claude_client"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    resp = MagicMock()
    resp.usage.input_tokens = input_tokens
    resp.usage.output_tokens = output_tokens
    return resp


# ---------------------------------------------------------------------------
# _compute_cost
# ---------------------------------------------------------------------------

class TestComputeCost:
    def test_sonnet_46(self) -> None:
        from apps.shared.claude_client import _compute_cost
        cost = _compute_cost("claude-sonnet-4-6", 1_000_000, 0)
        assert abs(cost - 3.0 * 0.92) < 1e-6

    def test_sonnet_46_suffix(self) -> None:
        from apps.shared.claude_client import _compute_cost
        cost = _compute_cost("claude-sonnet-4-6-20251001", 1_000_000, 0)
        assert abs(cost - 3.0 * 0.92) < 1e-6

    def test_haiku(self) -> None:
        from apps.shared.claude_client import _compute_cost
        cost = _compute_cost("claude-haiku-4-5", 0, 1_000_000)
        assert abs(cost - 4.0 * 0.92) < 1e-6

    def test_unknown_model_uses_default(self) -> None:
        from apps.shared.claude_client import _compute_cost
        cost = _compute_cost("claude-future-99", 1_000_000, 0)
        assert cost > 0

    def test_zero_tokens(self) -> None:
        from apps.shared.claude_client import _compute_cost
        assert _compute_cost("claude-sonnet-4-6", 0, 0) == 0.0

    def test_small_call_has_nonzero_cost(self) -> None:
        from apps.shared.claude_client import _compute_cost
        cost = _compute_cost("claude-sonnet-4-6", 1000, 500)
        assert cost > 0


# ---------------------------------------------------------------------------
# _write_usage
# ---------------------------------------------------------------------------

class TestWriteUsage:
    @patch(f"{_MOD}.date")
    @patch(f"{_MOD}.datetime")
    def test_writes_correct_row(self, mock_dt: MagicMock, mock_date: MagicMock, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_date.today.return_value.isoformat.return_value = "2026-06-01"
        mock_dt.now.return_value.isoformat.return_value = "2026-06-01T08:45:00+00:00"

        mock_sb = MagicMock()
        mock_sb.table.return_value.insert.return_value.execute.return_value = MagicMock()

        monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")

        with patch("supabase.create_client", return_value=mock_sb):
            from apps.shared.claude_client import _write_usage
            _write_usage("email_analyzer", "claude-sonnet-4-6", 1000, 500)

        mock_sb.table.assert_called_once_with("token_usage")
        inserted = mock_sb.table.return_value.insert.call_args[0][0]
        assert inserted["agent_name"] == "email_analyzer"
        assert inserted["model"] == "claude-sonnet-4-6"
        assert inserted["input_tokens"] == 1000
        assert inserted["output_tokens"] == 500
        assert inserted["cost_eur"] > 0

    def test_does_not_raise_on_supabase_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SUPABASE_URL", "https://x.supabase.co")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-key")
        with patch("supabase.create_client", side_effect=Exception("network error")):
            from apps.shared.claude_client import _write_usage
            _write_usage("agent", "claude-sonnet-4-6", 100, 50)  # must not raise


# ---------------------------------------------------------------------------
# TrackedAnthropicClient / _TrackedMessages
# ---------------------------------------------------------------------------

class TestTrackedMessages:
    @patch(f"{_MOD}._write_usage")
    @patch("anthropic.Anthropic")
    def test_create_calls_inner_and_logs(self, mock_anthropic: MagicMock, mock_write: MagicMock) -> None:
        fake_response = _make_response(input_tokens=200, output_tokens=80)
        mock_anthropic.return_value.messages.create.return_value = fake_response

        from apps.shared.claude_client import TrackedAnthropicClient
        client = TrackedAnthropicClient("test_agent")
        result = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": "hello"}],
        )

        assert result is fake_response
        mock_write.assert_called_once_with(
            agent_name="test_agent",
            model="claude-sonnet-4-6",
            input_tokens=200,
            output_tokens=80,
        )

    @patch(f"{_MOD}._write_usage", side_effect=Exception("db down"))
    @patch("anthropic.Anthropic")
    def test_returns_response_even_if_write_fails(self, mock_anthropic: MagicMock, mock_write: MagicMock) -> None:
        fake_response = _make_response()
        mock_anthropic.return_value.messages.create.return_value = fake_response

        from apps.shared.claude_client import TrackedAnthropicClient
        client = TrackedAnthropicClient("test_agent")
        result = client.messages.create(model="claude-sonnet-4-6", max_tokens=50, messages=[])
        assert result is fake_response


class TestGetClient:
    @patch("anthropic.Anthropic")
    def test_returns_tracked_client(self, mock_anthropic: MagicMock) -> None:
        from apps.shared.claude_client import TrackedAnthropicClient, get_client
        client = get_client("my_agent")
        assert isinstance(client, TrackedAnthropicClient)
        assert client._agent_name == "my_agent"

    @patch("anthropic.Anthropic")
    def test_different_agent_names(self, mock_anthropic: MagicMock) -> None:
        from apps.shared.claude_client import get_client
        c1 = get_client("email_analyzer")
        c2 = get_client("relance_handler")
        assert c1._agent_name == "email_analyzer"
        assert c2._agent_name == "relance_handler"
