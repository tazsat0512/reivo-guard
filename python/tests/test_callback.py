"""Tests for LiteLLM callback integration."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from reivo_guard import ReivoGuard
from reivo_guard.guard import BudgetExceeded, LoopDetected


class TestReivoGuardInit:
    def test_default_init(self):
        guard = ReivoGuard()
        assert guard.total_requests == 0
        assert guard.total_cost_usd == 0.0
        assert guard.stats["budget_limit_usd"] is None

    def test_with_budget(self):
        guard = ReivoGuard(budget_limit_usd=50.0)
        assert guard.stats["budget_limit_usd"] == 50.0

    def test_stats(self):
        guard = ReivoGuard(budget_limit_usd=100.0)
        stats = guard.stats
        assert stats["total_requests"] == 0
        assert stats["budget_limit_usd"] == 100.0
        assert stats["budget_remaining_usd"] == 100.0


class TestBudgetEnforcement:
    def test_blocks_when_exceeded(self):
        guard = ReivoGuard(budget_limit_usd=1.0)
        # Simulate cost accumulation
        now = datetime.now()
        guard.log_success_event(
            {"response_cost": 1.5, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        # Next pre-call should raise
        with pytest.raises(BudgetExceeded) as exc_info:
            guard.log_pre_api_call(
                "gpt-4o",
                [{"role": "user", "content": "test"}],
                {},
            )
        assert exc_info.value.used == 1.5
        assert exc_info.value.limit == 1.0
        assert guard.blocked_requests == 1

    def test_custom_budget_handler(self):
        called = {}

        def handler(used, limit):
            called["used"] = used
            called["limit"] = limit

        guard = ReivoGuard(budget_limit_usd=1.0, on_budget_exceeded=handler)
        now = datetime.now()
        guard.log_success_event(
            {"response_cost": 2.0, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        # Should call handler instead of raising
        guard.log_pre_api_call("gpt-4o", [{"role": "user", "content": "x"}], {})
        assert called["used"] == 2.0
        assert called["limit"] == 1.0

    def test_no_limit_never_blocks(self):
        guard = ReivoGuard()  # No budget limit
        now = datetime.now()
        for _ in range(100):
            guard.log_success_event(
                {"response_cost": 100.0, "model": "gpt-4o"},
                MagicMock(),
                now,
                now,
            )
        # Should not raise
        guard.log_pre_api_call("gpt-4o", [{"role": "user", "content": "x"}], {})
        assert guard.blocked_requests == 0


class TestLoopDetection:
    def test_detects_repeated_prompts(self):
        guard = ReivoGuard(loop_threshold=3, loop_window=10)
        messages = [{"role": "user", "content": "same prompt"}]
        # First two calls are fine
        guard.log_pre_api_call("gpt-4o", messages, {})
        guard.log_pre_api_call("gpt-4o", messages, {})
        # Third identical call triggers loop
        with pytest.raises(LoopDetected) as exc_info:
            guard.log_pre_api_call("gpt-4o", messages, {})
        assert exc_info.value.match_count == 3

    def test_different_prompts_no_loop(self):
        guard = ReivoGuard(loop_threshold=3, loop_window=10)
        for i in range(10):
            guard.log_pre_api_call(
                "gpt-4o",
                [{"role": "user", "content": f"prompt {i}"}],
                {},
            )
        assert guard.blocked_requests == 0

    def test_custom_loop_handler(self):
        called = {}

        def handler(count, window):
            called["count"] = count
            called["window"] = window

        guard = ReivoGuard(loop_threshold=2, on_loop_detected=handler)
        messages = [{"role": "user", "content": "repeat"}]
        guard.log_pre_api_call("gpt-4o", messages, {})
        guard.log_pre_api_call("gpt-4o", messages, {})
        assert called["count"] == 2


class TestCostTracking:
    def test_tracks_cumulative_cost(self):
        guard = ReivoGuard(budget_limit_usd=100.0)
        now = datetime.now()
        guard.log_success_event(
            {"response_cost": 0.05, "model": "gpt-4o-mini"},
            MagicMock(),
            now,
            now,
        )
        guard.log_success_event(
            {"response_cost": 0.10, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        assert guard.total_requests == 2
        assert abs(guard.total_cost_usd - 0.15) < 1e-9
        stats = guard.stats
        assert stats["budget_used_usd"] == 0.15
        assert stats["budget_remaining_usd"] == 99.85

    def test_handles_missing_cost(self):
        guard = ReivoGuard()
        now = datetime.now()
        guard.log_success_event({"model": "gpt-4o"}, MagicMock(), now, now)
        assert guard.total_cost_usd == 0.0


class TestReset:
    def test_reset_clears_state(self):
        guard = ReivoGuard(budget_limit_usd=10.0)
        now = datetime.now()
        guard.log_success_event(
            {"response_cost": 5.0, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        guard.log_pre_api_call("gpt-4o", [{"role": "user", "content": "x"}], {})
        assert guard.total_requests == 1

        guard.reset()
        assert guard.total_requests == 0
        assert guard.total_cost_usd == 0.0
        assert guard.stats["budget_used_usd"] == 0.0


class TestAsyncHooks:
    @pytest.mark.asyncio
    async def test_async_pre_call_checks_budget(self):
        guard = ReivoGuard(budget_limit_usd=0.01)
        now = datetime.now()
        guard.log_success_event(
            {"response_cost": 1.0, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        with pytest.raises(BudgetExceeded):
            await guard.async_log_pre_api_call(
                "gpt-4o",
                [{"role": "user", "content": "x"}],
                {},
            )

    @pytest.mark.asyncio
    async def test_async_success_tracks_cost(self):
        guard = ReivoGuard()
        now = datetime.now()
        await guard.async_log_success_event(
            {"response_cost": 0.05, "model": "gpt-4o"},
            MagicMock(),
            now,
            now,
        )
        assert guard.total_cost_usd == 0.05
