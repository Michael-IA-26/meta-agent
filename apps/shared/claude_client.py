"""Tracked Anthropic client — intercepts every messages.create() call.

Usage:
    from apps.shared.claude_client import get_client
    client = get_client("my_agent")
    response = client.messages.create(model=..., messages=..., max_tokens=...)

Logs input_tokens, output_tokens and cost_eur to Supabase table `token_usage`.
Falls back silently if Supabase is unavailable so agents are never blocked.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timezone
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# EUR per token, by model prefix (input_rate, output_rate)
# Source: Anthropic pricing × 0.92 USD→EUR conversion
_PRICING: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (3.0 * 0.92 / 1_000_000, 15.0 * 0.92 / 1_000_000),
    "claude-sonnet-4-5": (3.0 * 0.92 / 1_000_000, 15.0 * 0.92 / 1_000_000),
    "claude-opus-4-7":   (15.0 * 0.92 / 1_000_000, 75.0 * 0.92 / 1_000_000),
    "claude-haiku-4-5":  (0.80 * 0.92 / 1_000_000,  4.0 * 0.92 / 1_000_000),
}
_DEFAULT_PRICING = (3.0 * 0.92 / 1_000_000, 15.0 * 0.92 / 1_000_000)


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    # Match on prefix so "claude-sonnet-4-6-20251001" still resolves correctly
    for prefix, (in_rate, out_rate) in _PRICING.items():
        if model.startswith(prefix):
            return round(input_tokens * in_rate + output_tokens * out_rate, 6)
    in_rate, out_rate = _DEFAULT_PRICING
    return round(input_tokens * in_rate + output_tokens * out_rate, 6)


def _write_usage(agent_name: str, model: str, input_tokens: int, output_tokens: int) -> None:
    cost_eur = _compute_cost(model, input_tokens, output_tokens)
    try:
        from supabase import create_client

        sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_KEY"],
        )
        sb.table("token_usage").insert({
            "agent_name": agent_name,
            "model": model,
            "date": date.today().isoformat(),
            "called_at": datetime.now(timezone.utc).isoformat(),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_eur": cost_eur,
        }).execute()
        logger.debug(
            "token_usage: %s | %s | in=%d out=%d cost=€%.4f",
            agent_name, model, input_tokens, output_tokens, cost_eur,
        )
    except Exception as exc:
        logger.warning("token_usage: write failed (non-blocking) — %s", exc)


class _TrackedMessages:
    """Thin proxy around anthropic.resources.Messages that logs usage after each call."""

    def __init__(self, inner: anthropic.Anthropic, agent_name: str) -> None:
        self._inner = inner
        self._agent_name = agent_name

    def create(self, **kwargs: Any) -> Any:
        response = self._inner.messages.create(**kwargs)
        try:
            usage = response.usage
            _write_usage(
                agent_name=self._agent_name,
                model=kwargs.get("model", "unknown"),
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
            )
        except Exception as exc:
            logger.warning("token_usage: usage extraction failed — %s", exc)
        return response


class TrackedAnthropicClient:
    """Drop-in replacement for `anthropic.Anthropic()` with token usage tracking."""

    def __init__(self, agent_name: str) -> None:
        self._agent_name = agent_name
        self._inner = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.messages = _TrackedMessages(self._inner, agent_name)


def get_client(agent_name: str) -> TrackedAnthropicClient:
    """Return a tracked Anthropic client tagged with *agent_name*."""
    return TrackedAnthropicClient(agent_name)
