"""Tests for budget degradation levels."""

from reivo_guard.degradation import get_degradation_level


class TestGetDegradationLevel:
    def test_normal(self):
        policy = get_degradation_level(30, 100)
        assert policy.level == "normal"
        assert not policy.force_aggressive_routing
        assert not policy.block_new_sessions
        assert not policy.block_all

    def test_aggressive(self):
        policy = get_degradation_level(85, 100)
        assert policy.level == "aggressive"
        assert policy.force_aggressive_routing
        assert not policy.block_new_sessions
        assert not policy.block_all

    def test_new_sessions_only(self):
        policy = get_degradation_level(96, 100)
        assert policy.level == "new_sessions_only"
        assert policy.force_aggressive_routing
        assert policy.block_new_sessions
        assert not policy.block_all

    def test_blocked(self):
        policy = get_degradation_level(100, 100)
        assert policy.level == "blocked"
        assert policy.force_aggressive_routing
        assert policy.block_new_sessions
        assert policy.block_all

    def test_over_budget(self):
        policy = get_degradation_level(150, 100)
        assert policy.level == "blocked"

    def test_zero_limit(self):
        policy = get_degradation_level(0, 0)
        assert policy.level == "blocked"

    def test_boundary_80(self):
        policy = get_degradation_level(80, 100)
        assert policy.level == "aggressive"

    def test_boundary_79(self):
        policy = get_degradation_level(79, 100)
        assert policy.level == "normal"

    def test_boundary_95(self):
        policy = get_degradation_level(95, 100)
        assert policy.level == "new_sessions_only"

    def test_usage_ratio(self):
        policy = get_degradation_level(42, 100)
        assert abs(policy.usage_ratio - 0.42) < 0.001
