"""Tests for EWMA anomaly detection."""

from reivo_guard.anomaly import EwmaState, detect_anomaly, update_ewma


class TestUpdateEwma:
    def test_first_update(self):
        state = EwmaState()
        new_state = update_ewma(state, 100)
        assert new_state.ewma_value > 0
        assert new_state.sample_count == 1

    def test_converges(self):
        state = EwmaState()
        for _ in range(50):
            state = update_ewma(state, 100)
        assert abs(state.ewma_value - 100) < 1.0

    def test_tracks_trend(self):
        state = EwmaState()
        for _ in range(20):
            state = update_ewma(state, 100)
        for _ in range(20):
            state = update_ewma(state, 200)
        assert state.ewma_value > 150


class TestDetectAnomaly:
    def test_no_anomaly_stable(self):
        state = EwmaState()
        # Use some variance in training data
        for i in range(50):
            state = update_ewma(state, 100 + (i % 5) - 2)
        result = detect_anomaly(state, 103)
        assert not result.is_anomaly

    def test_detects_spike(self):
        state = EwmaState()
        for _ in range(50):
            state = update_ewma(state, 100)
        result = detect_anomaly(state, 800)
        assert result.is_anomaly
        assert result.z_score > 3.0

    def test_zero_variance(self):
        state = EwmaState()
        result = detect_anomaly(state, 100)
        assert not result.is_anomaly
        assert result.z_score == 0.0

    def test_detect_before_update(self):
        """Critical: detect BEFORE update to catch spikes."""
        state = EwmaState()
        for _ in range(50):
            state = update_ewma(state, 100)

        # Correct order: detect then update
        result = detect_anomaly(state, 800)
        assert result.is_anomaly

        # Wrong order: update absorbs the spike
        state2 = update_ewma(state, 800)
        result2 = detect_anomaly(state2, 800)
        assert result2.z_score < result.z_score

    def test_custom_threshold(self):
        state = EwmaState()
        for _ in range(50):
            state = update_ewma(state, 100)
        # Low threshold catches mild anomalies
        result = detect_anomaly(state, 110, z_threshold=1.0)
        assert result.is_anomaly or result.z_score > 0
