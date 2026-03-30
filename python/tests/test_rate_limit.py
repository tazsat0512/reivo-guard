"""Tests for rate limiting and integrated Guard features."""

import time

from reivo_guard import Guard, AnomalyDetected, RateLimitExceeded


class TestRateLimit:
    def test_blocks_when_exceeded(self):
        guard = Guard(rate_limit=3, rate_limit_window=60)
        assert guard.before().allowed
        assert guard.before().allowed
        assert guard.before().allowed
        decision = guard.before()
        assert not decision.allowed
        assert "Rate limit" in (decision.reason or "")

    def test_raises_when_exceeded(self):
        guard = Guard(rate_limit=2, rate_limit_window=60, raise_on_block=True)
        guard.before()
        guard.before()
        try:
            guard.before()
            assert False, "Should have raised"
        except RateLimitExceeded as e:
            assert e.limit == 2

    def test_resets_after_window(self):
        guard = Guard(rate_limit=2, rate_limit_window=0.1)
        guard.before()
        guard.before()
        assert not guard.before().allowed
        time.sleep(0.15)
        assert guard.before().allowed

    def test_no_rate_limit(self):
        guard = Guard()
        for _ in range(100):
            assert guard.before().allowed

    def test_validation(self):
        try:
            Guard(rate_limit=0)
            assert False, "Should have raised"
        except ValueError:
            pass


class TestAnomalyInGuard:
    def test_detects_spike(self):
        guard = Guard(enable_anomaly_detection=True)
        # Build baseline
        for _ in range(50):
            guard.before(token_count=100)
        # Spike
        decision = guard.before(token_count=800)
        assert not decision.allowed
        assert "Anomaly" in (decision.reason or "")
        assert decision.anomaly is not None

    def test_no_anomaly_stable(self):
        guard = Guard(enable_anomaly_detection=True)
        # Use some variance so EWMA doesn't converge too tight
        for i in range(50):
            guard.before(token_count=100 + (i % 5) - 2)
        decision = guard.before(token_count=103)
        assert decision.allowed

    def test_disabled_by_default(self):
        guard = Guard()
        for _ in range(50):
            guard.before(token_count=100)
        # No anomaly detection, so spike should pass
        decision = guard.before(token_count=800)
        assert decision.allowed

    def test_raises_on_anomaly(self):
        guard = Guard(enable_anomaly_detection=True, raise_on_block=True)
        for _ in range(50):
            guard.before(token_count=100)
        try:
            guard.before(token_count=800)
            assert False, "Should have raised"
        except AnomalyDetected as e:
            assert e.z_score > 3.0

    def test_stats_include_ewma(self):
        guard = Guard(enable_anomaly_detection=True)
        guard.before(token_count=100)
        stats = guard.stats
        assert "ewma_value" in stats
        assert "ewma_samples" in stats


class TestDegradationInGuard:
    def test_decision_includes_level(self):
        guard = Guard(budget_limit_usd=100)
        decision = guard.before()
        assert decision.degradation_level == "normal"

    def test_aggressive_level(self):
        guard = Guard(budget_limit_usd=100)
        guard.after(cost_usd=85)
        decision = guard.before()
        assert decision.degradation_level == "aggressive"

    def test_no_level_without_budget(self):
        guard = Guard()
        decision = guard.before()
        assert decision.degradation_level is None

    def test_degradation_property(self):
        guard = Guard(budget_limit_usd=100)
        guard.after(cost_usd=96)
        deg = guard.degradation
        assert deg is not None
        assert deg.level == "new_sessions_only"
        assert deg.block_new_sessions

    def test_stats_include_level(self):
        guard = Guard(budget_limit_usd=100)
        guard.after(cost_usd=50)
        stats = guard.stats
        assert stats["degradation_level"] == "normal"


class TestGuardReset:
    def test_reset_clears_all(self):
        guard = Guard(
            budget_limit_usd=100,
            enable_anomaly_detection=True,
            rate_limit=10,
        )
        guard.before(token_count=100)
        guard.after(cost_usd=50)
        guard.reset()
        stats = guard.stats
        assert stats["total_requests"] == 0
        assert stats["total_cost_usd"] == 0
        assert stats["budget_used_usd"] == 0
        assert stats["ewma_samples"] == 0
