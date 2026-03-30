"""Tests for CrewAI integration."""

from reivo_guard.crewai import ReivoCrewCallback
from reivo_guard import BudgetExceeded


class FakeStepOutput:
    def __init__(self, text):
        self.output = text


class TestReivoCrewCallback:
    def test_basic_passthrough(self):
        cb = ReivoCrewCallback(budget_limit_usd=10.0)
        result = cb("Hello world")
        assert result == "Hello world"

    def test_budget_block(self):
        cb = ReivoCrewCallback(budget_limit_usd=0.01, default_model="gpt-4o")
        # Each call uses different text to avoid loop detection
        try:
            for i in range(20):
                cb(f"unique message number {i} with padding " + "x" * 500)
        except BudgetExceeded:
            pass  # Expected
        assert cb.stats["blocked_requests"] >= 1

    def test_loop_detection(self):
        cb = ReivoCrewCallback(loop_threshold=3)
        try:
            for _ in range(5):
                cb("same message")
        except Exception:
            pass
        assert cb.stats["blocked_requests"] >= 1

    def test_extracts_text_from_object(self):
        cb = ReivoCrewCallback(budget_limit_usd=100.0)
        output = FakeStepOutput("test output")
        result = cb(output)
        assert result is output

    def test_custom_on_block(self):
        blocked_reasons = []
        cb = ReivoCrewCallback(
            budget_limit_usd=0.001,
            default_model="gpt-4o",
            on_block=lambda d: blocked_reasons.append(d.reason),
        )
        for _ in range(20):
            cb("x" * 1000)
        assert len(blocked_reasons) > 0

    def test_rate_limit(self):
        cb = ReivoCrewCallback(rate_limit=3, rate_limit_window=60)
        cb("a")
        cb("b")
        cb("c")
        try:
            cb("d")
            assert False, "Should have raised"
        except RuntimeError:
            pass

    def test_stats(self):
        cb = ReivoCrewCallback(budget_limit_usd=100.0)
        cb("hello")
        stats = cb.stats
        assert "total_requests" in stats
        assert "budget_used_usd" in stats

    def test_guard_access(self):
        cb = ReivoCrewCallback()
        assert cb.guard is not None
