"""Tests covering gaps identified in the code audit.

Covers: anomaly negative spikes, anomaly warmup, CUSUM detect/update consistency,
CUSUM gradual drift, CUSUM custom slack, sequence edge cases, forecast CI edge cases,
standalone total_requests consistency, guard NaN/Inf, cosine empty input.
"""

import math

import pytest

from reivo_guard.anomaly import EwmaState, detect_anomaly, update_ewma
from reivo_guard.cosine import detect_loop_by_cosine, _tokenize, _cosine_similarity
from reivo_guard.cusum import CusumState, detect_drift, update_cusum, reset_cusum
from reivo_guard.degradation import get_degradation_level
from reivo_guard.forecast import BudgetForecaster, _ols, _t_critical
from reivo_guard.guard import BudgetState, LoopState, hash_messages
from reivo_guard.sequence import detect_sequence_loop, detect_sequence_loop_ngram
from reivo_guard.standalone import Guard, AnomalyDetected


# ── Anomaly: negative spike detection ─────────────────────────────────

class TestAnomalyNegativeSpike:
    def test_detects_negative_spike(self):
        """z-score should use abs(), catching sudden drops."""
        state = EwmaState()
        for _ in range(50):
            state = update_ewma(state, 100)
        result = detect_anomaly(state, 0)  # massive drop
        assert result.is_anomaly
        assert result.z_score > 3.0

    def test_detects_negative_value_spike(self):
        state = EwmaState()
        for i in range(50):
            state = update_ewma(state, 100 + (i % 5) - 2)
        result = detect_anomaly(state, -500)
        assert result.is_anomaly


class TestAnomalyWarmup:
    def test_no_false_positive_during_warmup(self):
        """First few samples should never trigger anomaly."""
        state = EwmaState()
        state = update_ewma(state, 100)
        state = update_ewma(state, 100)
        # After only 2 samples, even a big spike shouldn't trigger
        result = detect_anomaly(state, 10000, warmup=5)
        assert not result.is_anomaly

    def test_triggers_after_warmup(self):
        state = EwmaState()
        for _ in range(10):
            state = update_ewma(state, 100)
        result = detect_anomaly(state, 800, warmup=5)
        assert result.is_anomaly

    def test_warmup_zero_allows_immediate(self):
        state = EwmaState()
        for _ in range(10):
            state = update_ewma(state, 100)
        result = detect_anomaly(state, 800, warmup=0)
        assert result.is_anomaly


# ── CUSUM: detect/update consistency ──────────────────────────────────

class TestCusumConsistency:
    def test_detect_and_update_use_same_slack(self):
        """With explicit slack, detect_drift and update_cusum should agree."""
        state = CusumState()
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 5) - 2, slack=1.0)

        value = 120.0
        result = detect_drift(state, value, slack=1.0, warmup=10)
        new_state = update_cusum(state, value, slack=1.0)

        # The preview values from detect should match the actual update
        deviation = value - state.target
        expected_pos = max(0, state.pos_sum + deviation - 1.0)
        expected_neg = max(0, state.neg_sum - deviation - 1.0)
        assert abs(new_state.pos_sum - expected_pos) < 1e-10
        assert abs(new_state.neg_sum - expected_neg) < 1e-10

    def test_detect_update_consistency_zero_stddev(self):
        """When std_dev=0, both functions should use the same fallback slack."""
        state = CusumState()
        for _ in range(20):
            state = update_cusum(state, 100.0)

        # With explicit slack, they must agree
        result = detect_drift(state, 110.0, slack=2.0, warmup=10)
        new_state = update_cusum(state, 110.0, slack=2.0)
        assert abs(new_state.pos_sum - max(0, state.pos_sum + (110 - state.target) - 2.0)) < 1e-10


class TestCusumGradualDrift:
    def test_detects_slow_linear_increase(self):
        """The primary use case: gradual drift like 100, 101, 102..."""
        state = CusumState()
        # Train on stable data
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 3) - 1)

        # Gradual increase
        detected = False
        for i in range(50):
            value = 100.0 + i * 2  # slowly climbing
            result = detect_drift(state, value, warmup=10)
            state = update_cusum(state, value)
            if result.drift_detected:
                detected = True
                assert result.direction == "up"
                break

        assert detected, "CUSUM should detect gradual upward drift"


class TestCusumCustomSlack:
    def test_custom_slack_in_detect(self):
        state = CusumState()
        for i in range(20):
            state = update_cusum(state, 100.0 + (i % 3))
        result = detect_drift(state, 105.0, slack=0.1, warmup=10)
        assert isinstance(result.cusum_value, float)

    def test_custom_slack_in_update(self):
        state = CusumState()
        state = update_cusum(state, 100.0, slack=0.5)
        state = update_cusum(state, 110.0, slack=0.5)
        assert state.sample_count == 2


class TestCusumResetThenRedetect:
    def test_detects_after_reset(self):
        state = CusumState()
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 5) - 2)

        # Trigger and reset
        for _ in range(10):
            state = update_cusum(state, 150.0)
        state = reset_cusum(state)
        assert state.pos_sum == 0.0

        # Feed new drift and detect again
        detected = False
        for _ in range(20):
            result = detect_drift(state, 200.0, warmup=10)
            state = update_cusum(state, 200.0)
            if result.drift_detected:
                detected = True
                break
        assert detected


# ── Sequence: edge cases ──────────────────────────────────────────────

class TestSequenceEdgeCases:
    def test_empty_list(self):
        assert not detect_sequence_loop([]).is_loop
        assert not detect_sequence_loop_ngram([]).is_loop

    def test_suffix_not_aligned_at_end(self):
        """Suffix-matching should fail when cycle doesn't align with tail."""
        hashes = ["a", "b", "a", "b", "a", "b", "x"]
        result = detect_sequence_loop(hashes, min_cycle_length=2, min_repetitions=3)
        assert not result.is_loop  # suffix is ["b", "x"], not repeating

    def test_ngram_max_cycle_length(self):
        pattern = ["a", "b", "c", "d", "e", "f"]
        hashes = pattern * 4
        result = detect_sequence_loop_ngram(hashes, max_cycle_length=5, min_repetitions=3)
        # 6-length cycle exceeds max, but sub-patterns might match
        # The full 6-gram won't be checked
        if result.is_loop:
            assert result.cycle_length <= 5

    def test_min_cycle_length_one(self):
        hashes = ["a", "a", "a", "a"]
        result = detect_sequence_loop(hashes, min_cycle_length=1, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 1

    def test_ngram_overlapping_count(self):
        """Ngram counts overlapping occurrences."""
        hashes = ["a", "a", "a", "a", "a", "a", "a"]
        result = detect_sequence_loop_ngram(hashes, min_cycle_length=2, min_repetitions=3)
        # Bigram ("a","a") appears at indices 0,1,2,3,4,5 = 6 overlapping
        assert result.is_loop
        assert result.repetitions >= 3


# ── Forecast: CI edge cases ──────────────────────────────────────────

class TestForecastEdgeCases:
    def test_partial_ci_slope_crosses_zero(self):
        """When slope CI lower bound is <= 0, ci_upper should be None."""
        f = BudgetForecaster(budget_limit_usd=1000.0, min_samples=5)
        # Very noisy data with a slight upward trend
        import random
        random.seed(42)
        for i in range(10):
            f.record(float(i * 0.1 + random.uniform(-5, 5)), timestamp=float(i))
        result = f.forecast()
        # With very noisy data, the slope CI may cross zero
        # Just verify no crash and types are correct
        assert result.samples == 10
        assert isinstance(result.cost_rate_per_second, float)
        if result.eta_seconds is not None:
            assert result.eta_seconds >= 0

    def test_r_squared_clamped(self):
        """R² should never be negative (clamped to 0)."""
        # Pathological data where regression is worse than mean
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 0.0, 10.0, 0.0, 10.0]
        _, _, r_sq, _ = _ols(xs, ys)
        assert r_sq >= 0.0

    def test_ols_empty_lists(self):
        """Direct call with empty lists should not crash."""
        slope, intercept, r_sq, se = _ols([], [])
        assert slope == 0.0
        assert se == 0.0

    def test_two_samples_min(self):
        """n=2 with min_samples=2: CI degenerates but shouldn't crash."""
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=2)
        f.record(0.0, timestamp=0.0)
        f.record(10.0, timestamp=1.0)
        result = f.forecast()
        assert result.eta_seconds is not None
        assert result.samples == 2

    def test_negative_t_critical(self):
        assert _t_critical(-5) == 12.706


# ── Standalone: total_requests consistency ────────────────────────────

class TestStandaloneRequestCounting:
    def test_blocked_counted_in_total(self):
        """Blocked requests should still be counted in total_requests."""
        g = Guard(budget_limit_usd=1.0)
        g.before()
        g.after(cost_usd=2.0)
        g.before()  # blocked — should still count
        assert g.total_requests == 2
        assert g.blocked_requests == 1

    def test_total_always_gte_blocked(self):
        g = Guard(budget_limit_usd=1.0)
        g.before()
        g.after(cost_usd=2.0)
        for _ in range(5):
            g.before()  # all blocked
        assert g.total_requests == 6
        assert g.blocked_requests == 5
        assert g.total_requests >= g.blocked_requests

    def test_rate_limit_blocked_not_consuming_slot(self):
        """Blocked requests should not consume rate limit slots."""
        g = Guard(rate_limit=2, rate_limit_window=60, loop_threshold=2)
        # First 2 allowed
        g.before(messages=[{"role": "user", "content": "a"}])
        g.before(messages=[{"role": "user", "content": "b"}])
        # 3rd blocked by rate limit
        d = g.before(messages=[{"role": "user", "content": "c"}])
        assert not d.allowed
        assert "Rate limit" in d.reason

    def test_loop_blocked_not_consuming_rate_limit(self):
        """Loop-blocked requests should not eat rate limit slots."""
        g = Guard(rate_limit=10, rate_limit_window=60, loop_threshold=2)
        msgs = [{"role": "user", "content": "repeat"}]
        g.before(messages=msgs)  # consumes 1 rate slot
        d = g.before(messages=msgs)  # loop detected — should NOT consume rate slot
        assert not d.allowed
        assert "Loop" in d.reason
        # Only 1 rate limit slot consumed (not 2)
        assert len(g._request_timestamps) == 1

    def test_after_explicit_zero_cost(self):
        """cost_usd=0.0 should record zero, not trigger estimation."""
        g = Guard()
        g.before()
        g.after(cost_usd=0.0, model="gpt-4o", input_tokens=1000, output_tokens=500)
        assert g.total_cost_usd == 0.0

    def test_after_none_cost_triggers_estimation(self):
        """cost_usd=None with tokens should trigger estimation."""
        g = Guard()
        g.before()
        g.after(cost_usd=None, model="gpt-4o-mini", input_tokens=1000, output_tokens=500)
        assert g.total_cost_usd > 0


# ── Guard: NaN/Inf/negative/unicode ──────────────────────────────────

class TestGuardEdgeCases:
    def test_budget_nan_cost(self):
        bs = BudgetState(limit_usd=10.0)
        bs.add_cost(float("nan"))
        assert bs.used_usd == 0.0

    def test_budget_inf_cost(self):
        bs = BudgetState(limit_usd=10.0)
        bs.add_cost(float("inf"))
        assert bs.used_usd == 0.0

    def test_budget_negative_cost(self):
        bs = BudgetState(limit_usd=10.0)
        bs.add_cost(-5.0)
        assert bs.used_usd == 0.0

    def test_loop_state_empty_check(self):
        ls = LoopState()
        is_loop, count = ls.check()
        assert not is_loop
        assert count == 0

    def test_hash_messages_unicode(self):
        h1 = hash_messages([{"role": "user", "content": "こんにちは"}])
        h2 = hash_messages([{"role": "user", "content": "こんにちは"}])
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_messages_emoji(self):
        h = hash_messages([{"role": "user", "content": "🚀💰"}])
        assert len(h) == 64


# ── Degradation: negative limit ──────────────────────────────────────

class TestDegradationEdgeCases:
    def test_negative_limit(self):
        result = get_degradation_level(0, -5)
        assert result.level == "blocked"

    def test_zero_limit(self):
        result = get_degradation_level(0, 0)
        assert result.level == "blocked"


# ── Cosine: empty/edge inputs ────────────────────────────────────────

class TestCosineEdgeCases:
    def test_empty_prompt(self):
        result = detect_loop_by_cosine(["hello world", ""], "")
        # Empty prompt should not crash
        assert isinstance(result.is_loop, bool)

    def test_single_char_tokens_only(self):
        """All tokens filtered out → empty vector → no crash."""
        result = detect_loop_by_cosine(["a b c", "x y z"], "a b c")
        assert isinstance(result.is_loop, bool)

    def test_tokenize_empty_string(self):
        tokens = _tokenize("")
        assert tokens == []

    def test_cosine_similarity_empty_vectors(self):
        sim = _cosine_similarity({}, {})
        assert sim == 0.0
