"""Tests for CUSUM change point detection."""

import math

from reivo_guard.cusum import (
    CusumResult,
    CusumState,
    detect_drift,
    reset_cusum,
    update_cusum,
)


class TestUpdateCusum:
    def test_initial_update(self):
        state = CusumState()
        new = update_cusum(state, 10.0)
        assert new.sample_count == 1
        assert new.target == 10.0
        assert new.sum_values == 10.0

    def test_running_mean(self):
        state = CusumState()
        for v in [10.0, 20.0, 30.0]:
            state = update_cusum(state, v)
        assert abs(state.target - 20.0) < 1e-10
        assert state.sample_count == 3

    def test_cusum_sums_accumulate(self):
        state = CusumState()
        # Feed stable values, then a spike
        for _ in range(20):
            state = update_cusum(state, 100.0)
        # pos_sum and neg_sum should be near 0 after stable period
        # (slack absorbs small deviations)
        assert state.pos_sum < 10  # Should be small


class TestDetectDrift:
    def test_warmup_period(self):
        state = CusumState()
        for _ in range(5):
            state = update_cusum(state, 100.0)
        result = detect_drift(state, 200.0, warmup=10)
        assert not result.drift_detected

    def test_no_drift_stable(self):
        state = CusumState()
        for i in range(20):
            v = 100.0 + (i % 3) - 1  # slight variation
            state = update_cusum(state, v)
        result = detect_drift(state, 101.0, warmup=10)
        assert not result.drift_detected

    def test_upward_drift(self):
        state = CusumState()
        # Train on stable values
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 5) - 2)

        # Inject persistent upward shift
        for _ in range(20):
            result = detect_drift(state, 150.0, warmup=10)
            state = update_cusum(state, 150.0)
            if result.drift_detected:
                break

        assert result.drift_detected
        assert result.direction == "up"
        assert result.cusum_value > result.threshold

    def test_downward_drift(self):
        state = CusumState()
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 5) - 2)

        for _ in range(20):
            result = detect_drift(state, 50.0, warmup=10)
            state = update_cusum(state, 50.0)
            if result.drift_detected:
                break

        assert result.drift_detected
        assert result.direction == "down"

    def test_custom_threshold(self):
        state = CusumState()
        for i in range(20):
            state = update_cusum(state, 100.0 + (i % 3))

        # Very high threshold — shouldn't trigger easily
        result = detect_drift(state, 110.0, threshold=10000.0, warmup=10)
        assert not result.drift_detected

    def test_result_fields(self):
        state = CusumState()
        for i in range(20):
            state = update_cusum(state, 100.0 + (i % 5) - 2)
        result = detect_drift(state, 105.0, warmup=10)
        assert result.threshold > 0
        assert isinstance(result.deviation_from_target, float)


class TestResetCusum:
    def test_reset_keeps_stats(self):
        state = CusumState()
        for _ in range(10):
            state = update_cusum(state, 100.0)

        reset = reset_cusum(state)
        assert reset.pos_sum == 0.0
        assert reset.neg_sum == 0.0
        assert reset.target == state.target
        assert reset.sample_count == state.sample_count
        assert reset.sum_values == state.sum_values
        assert reset.sum_sq_values == state.sum_sq_values

    def test_reset_allows_fresh_detection(self):
        state = CusumState()
        for i in range(30):
            state = update_cusum(state, 100.0 + (i % 5) - 2)

        # Trigger drift
        for _ in range(10):
            state = update_cusum(state, 150.0)

        # Reset and verify sums are cleared
        state = reset_cusum(state)
        assert state.pos_sum == 0.0
        assert state.neg_sum == 0.0


class TestEdgeCases:
    def test_zero_std_dev(self):
        """All identical values → std_dev=0 → should use fallback."""
        state = CusumState()
        for _ in range(20):
            state = update_cusum(state, 100.0)
        result = detect_drift(state, 100.0, warmup=10)
        assert not result.drift_detected
        assert result.threshold > 0

    def test_zero_target(self):
        """Target near zero should still work."""
        state = CusumState()
        for _ in range(20):
            state = update_cusum(state, 0.0)
        result = detect_drift(state, 5.0, warmup=10)
        # Should have a valid threshold (fallback for zero target)
        assert result.threshold > 0

    def test_negative_values(self):
        state = CusumState()
        for i in range(20):
            state = update_cusum(state, -50.0 + (i % 3))
        result = detect_drift(state, -45.0, warmup=10)
        assert isinstance(result, CusumResult)
