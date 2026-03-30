"""LiteLLM custom callback for Reivo guardrails.

Usage:
    import litellm
    from reivo_guard import ReivoGuard

    litellm.callbacks = [ReivoGuard(budget_limit_usd=50.0)]
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from .guard import BudgetExceeded, LoopDetected, _hash_messages
from .standalone import Guard

logger = logging.getLogger("reivo_guard")


class ReivoGuard:
    """LiteLLM callback that enforces budget limits and detects loops.

    Args:
        budget_limit_usd: Maximum cumulative spend in USD. None = unlimited.
        loop_window: Number of recent requests to check for loops.
        loop_threshold: Number of identical prompts within the window to trigger.
        on_budget_exceeded: Callback ``(used, limit) -> None``. Default raises.
        on_loop_detected: Callback ``(count, window) -> None``. Default raises.
    """

    def __init__(
        self,
        budget_limit_usd: Optional[float] = None,
        loop_window: int = 20,
        loop_threshold: int = 3,
        on_budget_exceeded: Optional[Any] = None,
        on_loop_detected: Optional[Any] = None,
    ) -> None:
        self._guard = Guard(
            budget_limit_usd=budget_limit_usd,
            loop_window=loop_window,
            loop_threshold=loop_threshold,
            raise_on_block=False,
        )
        self._on_budget_exceeded = on_budget_exceeded
        self._on_loop_detected = on_loop_detected

    # ── LiteLLM sync hooks ──────────────────────────────────────────

    def log_pre_api_call(
        self, model: str, messages: Any, kwargs: dict[str, Any]
    ) -> None:
        """Called before each LLM request. Checks budget and loops."""
        prompt_hash = _hash_messages(messages)
        decision = self._guard.before(prompt_hash=prompt_hash)

        if not decision.allowed:
            reason = decision.reason or ""
            if "Budget exceeded" in reason:
                if self._on_budget_exceeded:
                    self._on_budget_exceeded(
                        self._guard._budget.used_usd,
                        self._guard._budget.limit_usd,
                    )
                    return
                raise BudgetExceeded(
                    self._guard._budget.used_usd,
                    self._guard._budget.limit_usd or 0,
                )
            else:
                window = len(self._guard._loop.hashes)
                count = sum(
                    1
                    for h in self._guard._loop.hashes
                    if h == self._guard._loop.hashes[-1]
                )
                if self._on_loop_detected:
                    self._on_loop_detected(count, window)
                    return
                raise LoopDetected(count, window)

    def log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Called after a successful LLM response. Tracks cost."""
        raw_cost = kwargs.get("response_cost", 0) or 0
        try:
            cost = max(0.0, float(raw_cost))
        except (TypeError, ValueError):
            cost = 0.0
        self._guard.after(cost_usd=cost)

        logger.debug(
            "reivo-guard: %s cost=$%.6f total=$%.4f",
            kwargs.get("model", "unknown"),
            cost,
            self._guard._budget.used_usd,
        )

    def log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Called after a failed LLM request."""
        pass  # total_requests already incremented in log_pre_api_call → before()
        logger.warning(
            "reivo-guard: request failed model=%s", kwargs.get("model", "unknown")
        )

    # ── LiteLLM async hooks ─────────────────────────────────────────

    async def async_log_pre_api_call(
        self, model: str, messages: Any, kwargs: dict[str, Any]
    ) -> None:
        """Async version of pre-call check."""
        self.log_pre_api_call(model, messages, kwargs)

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Async version of success tracking."""
        self.log_success_event(kwargs, response_obj, start_time, end_time)

    async def async_log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """Async version of failure tracking."""
        self.log_failure_event(kwargs, response_obj, start_time, end_time)

    # ── Utility ─────────────────────────────────────────────────────

    @property
    def total_requests(self) -> int:
        return self._guard.total_requests

    @property
    def total_cost_usd(self) -> float:
        return self._guard.total_cost_usd

    @property
    def blocked_requests(self) -> int:
        return self._guard.blocked_requests

    @property
    def stats(self) -> dict[str, Any]:
        """Return current guard statistics."""
        return self._guard.stats

    def reset(self) -> None:
        """Reset all state. Useful for testing."""
        self._guard.reset()
