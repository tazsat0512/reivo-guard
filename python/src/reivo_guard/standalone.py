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

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .anomaly import AnomalyResult, EwmaState, detect_anomaly, update_ewma
from .degradation import DegradationLevel, DegradationPolicy, get_degradation_level
from .guard import (
    BudgetExceeded,
    BudgetState,
    LoopDetected,
    LoopState,
    _hash_messages,
)


class AnomalyDetected(Exception):
    """Raised when an anomalous spike is detected."""

    def __init__(self, z_score: float, current_rate: float):
        self.z_score = z_score
        self.current_rate = current_rate
        super().__init__(f"Anomaly detected: z-score={z_score:.2f}, rate={current_rate}")


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, requests_in_window: int, limit: int):
        self.requests_in_window = requests_in_window
        self.limit = limit
        super().__init__(
            f"Rate limit exceeded: {requests_in_window}/{limit} requests"
        )


@dataclass
class GuardDecision:
    """Result of a before() check."""

    allowed: bool
    reason: Optional[str] = None
    budget_used_usd: float = 0.0
    budget_remaining_usd: Optional[float] = None
    degradation_level: Optional[DegradationLevel] = None
    anomaly: Optional[AnomalyResult] = None


class Guard:
    """Framework-agnostic guardrail with before/after pattern.

    Args:
        budget_limit_usd: Maximum cumulative spend in USD. None = unlimited.
        loop_window: Number of recent requests to check for loops.
        loop_threshold: Number of identical prompts within the window to trigger.
        raise_on_block: If True, before() raises exceptions instead of returning
            a non-allowed GuardDecision.
        enable_anomaly_detection: Enable EWMA anomaly detection on token counts.
        anomaly_z_threshold: Z-score threshold for anomaly detection. Default 3.0.
        rate_limit: Max requests per rate_limit_window seconds. None = unlimited.
        rate_limit_window: Time window in seconds for rate limiting. Default 60.
    """

    def __init__(
        self,
        budget_limit_usd: Optional[float] = None,
        loop_window: int = 20,
        loop_threshold: int = 3,
        raise_on_block: bool = False,
        enable_anomaly_detection: bool = False,
        anomaly_z_threshold: float = 3.0,
        rate_limit: Optional[int] = None,
        rate_limit_window: float = 60.0,
    ) -> None:
        from collections import deque

        if budget_limit_usd is not None and budget_limit_usd <= 0:
            raise ValueError("budget_limit_usd must be positive or None")
        if loop_window < 1:
            raise ValueError("loop_window must be >= 1")
        if loop_threshold < 2:
            raise ValueError("loop_threshold must be >= 2")
        if rate_limit is not None and rate_limit < 1:
            raise ValueError("rate_limit must be >= 1 or None")

        self._budget = BudgetState(limit_usd=budget_limit_usd)
        self._loop = LoopState(threshold=loop_threshold)
        self._loop.hashes = deque(maxlen=loop_window)
        self._raise_on_block = raise_on_block

        # Anomaly detection
        self._anomaly_enabled = enable_anomaly_detection
        self._anomaly_z_threshold = anomaly_z_threshold
        self._ewma = EwmaState()

        # Rate limiting
        self._rate_limit = rate_limit
        self._rate_limit_window = rate_limit_window
        self._request_timestamps: list[float] = []

        self.total_requests: int = 0
        self.total_cost_usd: float = 0.0
        self.blocked_requests: int = 0

    def before(
        self,
        messages: Any = None,
        prompt_hash: Optional[str] = None,
        token_count: Optional[int] = None,
    ) -> GuardDecision:
        """Check budget, loop, anomaly, and rate limit before an LLM call.

        Provide either ``messages`` (will be hashed) or a pre-computed
        ``prompt_hash``.  If neither is given, only budget/rate checks run.

        Args:
            messages: Messages list to hash for loop detection.
            prompt_hash: Pre-computed hash (alternative to messages).
            token_count: Token count for anomaly detection (e.g., prompt tokens).
        """
        remaining = self._budget.remaining_usd
        used = self._budget.used_usd

        # Degradation level
        degradation: Optional[DegradationPolicy] = None
        deg_level: Optional[DegradationLevel] = None
        if self._budget.limit_usd is not None:
            degradation = get_degradation_level(used, self._budget.limit_usd)
            deg_level = degradation.level

        # Budget check (blocked level)
        if self._budget.exceeded:
            self.blocked_requests += 1
            if self._raise_on_block:
                raise BudgetExceeded(used, self._budget.limit_usd or 0)
            return GuardDecision(
                allowed=False,
                reason=f"Budget exceeded: ${used:.4f} / ${self._budget.limit_usd:.2f}",
                budget_used_usd=used,
                budget_remaining_usd=0.0,
                degradation_level=deg_level,
            )

        # Rate limiting
        if self._rate_limit is not None:
            now = time.monotonic()
            cutoff = now - self._rate_limit_window
            self._request_timestamps = [
                t for t in self._request_timestamps if t > cutoff
            ]
            if len(self._request_timestamps) >= self._rate_limit:
                self.blocked_requests += 1
                if self._raise_on_block:
                    raise RateLimitExceeded(
                        len(self._request_timestamps), self._rate_limit
                    )
                return GuardDecision(
                    allowed=False,
                    reason=f"Rate limit exceeded: {len(self._request_timestamps)}/{self._rate_limit} requests in {self._rate_limit_window}s",
                    budget_used_usd=used,
                    budget_remaining_usd=remaining,
                    degradation_level=deg_level,
                )
            self._request_timestamps.append(now)

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
                    degradation_level=deg_level,
                )

        # Anomaly detection
        anomaly_result: Optional[AnomalyResult] = None
        if self._anomaly_enabled and token_count is not None:
            anomaly_result = detect_anomaly(
                self._ewma, token_count, self._anomaly_z_threshold
            )
            self._ewma = update_ewma(self._ewma, token_count)
            if anomaly_result.is_anomaly:
                self.blocked_requests += 1
                if self._raise_on_block:
                    raise AnomalyDetected(anomaly_result.z_score, token_count)
                return GuardDecision(
                    allowed=False,
                    reason=f"Anomaly detected: z-score={anomaly_result.z_score:.2f} (threshold={self._anomaly_z_threshold})",
                    budget_used_usd=used,
                    budget_remaining_usd=remaining,
                    degradation_level=deg_level,
                    anomaly=anomaly_result,
                )

        return GuardDecision(
            allowed=True,
            budget_used_usd=used,
            budget_remaining_usd=remaining,
            degradation_level=deg_level,
            anomaly=anomaly_result,
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
    def degradation(self) -> Optional[DegradationPolicy]:
        """Get current degradation policy. None if no budget limit."""
        if self._budget.limit_usd is None:
            return None
        return get_degradation_level(self._budget.used_usd, self._budget.limit_usd)

    @property
    def stats(self) -> dict[str, Any]:
        """Return current guard statistics."""
        result: dict[str, Any] = {
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
        if self._budget.limit_usd is not None:
            deg = get_degradation_level(self._budget.used_usd, self._budget.limit_usd)
            result["degradation_level"] = deg.level
        if self._anomaly_enabled:
            result["ewma_value"] = round(self._ewma.ewma_value, 4)
            result["ewma_samples"] = self._ewma.sample_count
        return result

    def reset(self) -> None:
        """Reset all state."""
        self._budget.used_usd = 0.0
        from collections import deque

        self._loop.hashes = deque(maxlen=self._loop.hashes.maxlen)
        self._ewma = EwmaState()
        self._request_timestamps = []
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
