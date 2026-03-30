"""Tests for the standalone Guard class."""

import pytest

from reivo_guard import Guard, GuardDecision, BudgetExceeded, LoopDetected
from reivo_guard.standalone import estimate_cost


class TestGuardDecision:
    def test_allowed_by_default(self):
        d = GuardDecision(allowed=True)
        assert d.allowed is True
        assert d.reason is None

    def test_blocked_with_reason(self):
        d = GuardDecision(allowed=False, reason="Over budget")
        assert d.allowed is False
        assert d.reason == "Over budget"


class TestGuardBefore:
    def test_allows_when_no_limits(self):
        g = Guard()
        decision = g.before(messages=[{"role": "user", "content": "hi"}])
        assert decision.allowed is True
        assert decision.budget_remaining_usd is None

    def test_blocks_on_budget_exceeded(self):
        g = Guard(budget_limit_usd=1.0)
        g.after(cost_usd=1.5)
        decision = g.before(messages=[{"role": "user", "content": "hi"}])
        assert decision.allowed is False
        assert "Budget exceeded" in (decision.reason or "")
        assert decision.budget_remaining_usd == 0.0

    def test_blocks_on_loop(self):
        g = Guard(loop_threshold=3)
        msgs = [{"role": "user", "content": "same prompt"}]
        g.before(messages=msgs)
        g.before(messages=msgs)
        decision = g.before(messages=msgs)
        assert decision.allowed is False
        assert "Loop detected" in (decision.reason or "")

    def test_raise_on_block_budget(self):
        g = Guard(budget_limit_usd=1.0, raise_on_block=True)
        g.after(cost_usd=2.0)
        with pytest.raises(BudgetExceeded):
            g.before(messages=[{"role": "user", "content": "hi"}])

    def test_raise_on_block_loop(self):
        g = Guard(loop_threshold=2, raise_on_block=True)
        msgs = [{"role": "user", "content": "repeat"}]
        g.before(messages=msgs)
        with pytest.raises(LoopDetected):
            g.before(messages=msgs)

    def test_with_prompt_hash(self):
        g = Guard(loop_threshold=2, raise_on_block=True)
        g.before(prompt_hash="abc123")
        with pytest.raises(LoopDetected):
            g.before(prompt_hash="abc123")

    def test_no_loop_check_without_messages(self):
        g = Guard()
        # Should only do budget check, not loop
        decision = g.before()
        assert decision.allowed is True

    def test_budget_remaining_tracks(self):
        g = Guard(budget_limit_usd=10.0)
        d1 = g.before()
        assert d1.budget_remaining_usd == 10.0
        g.after(cost_usd=3.0)
        d2 = g.before()
        assert d2.budget_remaining_usd == 7.0


class TestGuardAfter:
    def test_tracks_cost(self):
        g = Guard()
        g.before()  # total_requests incremented in before()
        g.after(cost_usd=0.5)
        g.before()
        g.after(cost_usd=0.3)
        assert g.total_cost_usd == pytest.approx(0.8)
        assert g.total_requests == 2

    def test_estimates_cost_from_tokens(self):
        g = Guard()
        g.after(model="gpt-4o-mini", input_tokens=1000, output_tokens=500)
        # 1000 * 0.15/1M + 500 * 0.60/1M = 0.00015 + 0.0003 = 0.00045
        assert g.total_cost_usd == pytest.approx(0.00045)

    def test_ignores_invalid_cost(self):
        g = Guard()
        g.after(cost_usd=float("nan"))
        g.after(cost_usd=float("inf"))
        g.after(cost_usd=-1.0)
        assert g.total_cost_usd == 0.0

    def test_prefers_explicit_cost_over_tokens(self):
        g = Guard()
        g.after(cost_usd=1.0, model="gpt-4o-mini", input_tokens=100, output_tokens=100)
        assert g.total_cost_usd == 1.0


class TestGuardStats:
    def test_stats_shape(self):
        g = Guard(budget_limit_usd=5.0)
        g.before()
        g.after(cost_usd=1.0)
        s = g.stats
        assert s["total_requests"] == 1
        assert s["total_cost_usd"] == 1.0
        assert s["budget_used_usd"] == 1.0
        assert s["budget_limit_usd"] == 5.0
        assert s["budget_remaining_usd"] == 4.0
        assert s["blocked_requests"] == 0

    def test_reset(self):
        g = Guard(budget_limit_usd=10.0)
        g.after(cost_usd=5.0)
        g.before(messages=[{"role": "user", "content": "x"}])
        g.reset()
        assert g.total_requests == 0
        assert g.total_cost_usd == 0.0
        assert g.stats["budget_used_usd"] == 0.0


class TestEstimateCost:
    def test_known_model(self):
        cost = estimate_cost("gpt-4o", 1_000_000, 1_000_000)
        assert cost == pytest.approx(12.5)  # 2.50 + 10.00

    def test_prefix_match(self):
        cost = estimate_cost("gpt-4o-2024-08-06", 1000, 1000)
        assert cost > 0

    def test_unknown_model(self):
        assert estimate_cost("unknown-model", 1000, 1000) == 0.0

    def test_zero_tokens(self):
        assert estimate_cost("gpt-4o", 0, 0) == 0.0

    def test_prefix_longest_match(self):
        """gpt-4o-mini-* should match gpt-4o-mini, not gpt-4o."""
        cost_mini = estimate_cost("gpt-4o-mini-2024-07-18", 1_000_000, 1_000_000)
        cost_4o = estimate_cost("gpt-4o-2024-08-06", 1_000_000, 1_000_000)
        # gpt-4o-mini: 0.15 + 0.60 = 0.75
        # gpt-4o: 2.50 + 10.00 = 12.50
        assert cost_mini == pytest.approx(0.75)
        assert cost_4o == pytest.approx(12.5)

    def test_gpt4_turbo_prefix(self):
        """gpt-4-turbo-* should match gpt-4-turbo, not gpt-4."""
        cost = estimate_cost("gpt-4-turbo-2024-04-09", 1_000_000, 1_000_000)
        assert cost == pytest.approx(40.0)  # 10 + 30


class TestParameterValidation:
    def test_negative_budget(self):
        with pytest.raises(ValueError, match="budget_limit_usd"):
            Guard(budget_limit_usd=-1.0)

    def test_zero_budget(self):
        with pytest.raises(ValueError, match="budget_limit_usd"):
            Guard(budget_limit_usd=0.0)

    def test_zero_loop_window(self):
        with pytest.raises(ValueError, match="loop_window"):
            Guard(loop_window=0)

    def test_loop_threshold_one(self):
        with pytest.raises(ValueError, match="loop_threshold"):
            Guard(loop_threshold=1)

    def test_valid_params(self):
        g = Guard(budget_limit_usd=0.01, loop_window=1, loop_threshold=2)
        assert g.stats["budget_limit_usd"] == 0.01


class TestBudgetBoundary:
    def test_exactly_at_limit(self):
        g = Guard(budget_limit_usd=1.0)
        g.after(cost_usd=1.0)
        decision = g.before()
        assert decision.allowed is False

    def test_just_under_limit(self):
        g = Guard(budget_limit_usd=1.0)
        g.after(cost_usd=0.999999)
        decision = g.before()
        assert decision.allowed is True

    def test_budget_check_before_loop_check(self):
        """When both budget exceeded and loop detected, budget takes priority."""
        g = Guard(budget_limit_usd=1.0, loop_threshold=2)
        msgs = [{"role": "user", "content": "same"}]
        g.before(messages=msgs)
        g.after(cost_usd=2.0)
        decision = g.before(messages=msgs)
        assert not decision.allowed
        assert "Budget" in (decision.reason or "")
