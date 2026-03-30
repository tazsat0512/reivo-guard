"""Standalone Guard class — framework-agnostic before/after pattern.

Usage:
    from reivo_guard import Guard

    guard = Guard(budget_limit_usd=10.0, loop_threshold=3)

    decision = guard.before(messages=[{"role": "user", "content": "Hello"}])
    if not decision.allowed:
        print(f"Blocked: {decision.reason}")
    else:
        response = call_llm(messages)
        guard.after(cost_usd=0.003)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .guard import (
    BudgetExceeded,
    BudgetState,
    LoopDetected,
    LoopState,
    _hash_messages,
)


@dataclass
class GuardDecision:
    """Result of a before() check."""

    allowed: bool
    reason: Optional[str] = None
    budget_used_usd: float = 0.0
    budget_remaining_usd: Optional[float] = None


class Guard:
    """Framework-agnostic guardrail with before/after pattern.

    Args:
        budget_limit_usd: Maximum cumulative spend in USD. None = unlimited.
        loop_window: Number of recent requests to check for loops.
        loop_threshold: Number of identical prompts within the window to trigger.
        raise_on_block: If True, before() raises BudgetExceeded/LoopDetected
            instead of returning a non-allowed GuardDecision.
    """

    def __init__(
        self,
        budget_limit_usd: Optional[float] = None,
        loop_window: int = 20,
        loop_threshold: int = 3,
        raise_on_block: bool = False,
    ) -> None:
        from collections import deque

        if budget_limit_usd is not None and budget_limit_usd <= 0:
            raise ValueError("budget_limit_usd must be positive or None")
        if loop_window < 1:
            raise ValueError("loop_window must be >= 1")
        if loop_threshold < 2:
            raise ValueError("loop_threshold must be >= 2")

        self._budget = BudgetState(limit_usd=budget_limit_usd)
        self._loop = LoopState(threshold=loop_threshold)
        self._loop.hashes = deque(maxlen=loop_window)
        self._raise_on_block = raise_on_block

        self.total_requests: int = 0
        self.total_cost_usd: float = 0.0
        self.blocked_requests: int = 0

    def before(
        self,
        messages: Any = None,
        prompt_hash: Optional[str] = None,
    ) -> GuardDecision:
        """Check budget and loop before an LLM call.

        Provide either ``messages`` (will be hashed) or a pre-computed
        ``prompt_hash``.  If neither is given, only the budget check runs.
        """
        remaining = self._budget.remaining_usd
        used = self._budget.used_usd

        # Budget check
        if self._budget.exceeded:
            self.blocked_requests += 1
            if self._raise_on_block:
                raise BudgetExceeded(used, self._budget.limit_usd or 0)
            return GuardDecision(
                allowed=False,
                reason=f"Budget exceeded: ${used:.4f} / ${self._budget.limit_usd:.2f}",
                budget_used_usd=used,
                budget_remaining_usd=0.0,
            )

        # Loop detection
        h = prompt_hash or (_hash_messages(messages) if messages is not None else None)
        if h is not None:
            self._loop.push(h)
            is_loop, count = self._loop.check()
            if is_loop:
                self.blocked_requests += 1
                window = len(self._loop.hashes)
                if self._raise_on_block:
                    raise LoopDetected(count, window)
                return GuardDecision(
                    allowed=False,
                    reason=f"Loop detected: {count} identical prompts in last {window} requests",
                    budget_used_usd=used,
                    budget_remaining_usd=remaining,
                )

        return GuardDecision(
            allowed=True,
            budget_used_usd=used,
            budget_remaining_usd=remaining,
        )

    def after(
        self,
        cost_usd: float = 0.0,
        model: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """Record cost after an LLM call.

        If ``cost_usd`` is 0 and token counts are provided, cost is estimated
        using ``estimate_cost()``.
        """
        if cost_usd <= 0 and (input_tokens > 0 or output_tokens > 0) and model:
            cost_usd = estimate_cost(model, input_tokens, output_tokens)

        import math

        if not math.isfinite(cost_usd) or cost_usd < 0:
            cost_usd = 0.0

        self._budget.add_cost(cost_usd)
        self.total_requests += 1
        self.total_cost_usd += cost_usd

    @property
    def stats(self) -> dict[str, Any]:
        """Return current guard statistics."""
        return {
            "total_requests": self.total_requests,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "budget_used_usd": round(self._budget.used_usd, 6),
            "budget_limit_usd": self._budget.limit_usd,
            "budget_remaining_usd": (
                round(self._budget.remaining_usd, 6)
                if self._budget.remaining_usd is not None
                else None
            ),
            "blocked_requests": self.blocked_requests,
        }

    def reset(self) -> None:
        """Reset all state."""
        self._budget.used_usd = 0.0
        from collections import deque

        self._loop.hashes = deque(maxlen=self._loop.hashes.maxlen)
        self.total_requests = 0
        self.total_cost_usd = 0.0
        self.blocked_requests = 0


# ── Simple cost estimation ────────────────────────────────────────────

# Prices per 1M tokens (input, output) in USD.
# Covers popular models; unknown models return 0.
_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-pro": (150.00, 600.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
    "claude-3-5-haiku-20241022": (0.80, 4.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-haiku-20240307": (0.25, 1.25),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    # Google
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD from token counts.

    Returns 0.0 for unknown models.
    """
    # Try exact match first, then longest prefix match
    pricing = _PRICING.get(model)
    if pricing is None:
        best_key = ""
        for key, val in _PRICING.items():
            if model.startswith(key) and len(key) > len(best_key):
                best_key = key
                pricing = val
    if pricing is None:
        return 0.0

    input_price, output_price = pricing
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000
