"""Tests for core guard logic."""

from reivo_guard.guard import (
    BudgetState,
    LoopState,
    check_budget,
    detect_loop,
    hash_messages,
)


class TestHashMessages:
    def test_consistent_hash(self):
        msgs = [{"role": "user", "content": "hello"}]
        h1 = hash_messages(msgs)
        h2 = hash_messages(msgs)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_messages_different_hash(self):
        h1 = hash_messages([{"role": "user", "content": "hello"}])
        h2 = hash_messages([{"role": "user", "content": "world"}])
        assert h1 != h2

    def test_handles_non_serializable(self):
        # Should not raise
        h = hash_messages(object())
        assert isinstance(h, str)


class TestLoopState:
    def test_no_loop_initially(self):
        state = LoopState(threshold=3)
        state.push("abc")
        is_loop, count = state.check()
        assert not is_loop
        assert count == 1

    def test_detects_loop(self):
        state = LoopState(threshold=3)
        for _ in range(3):
            state.push("same-hash")
        is_loop, count = state.check()
        assert is_loop
        assert count == 3

    def test_different_hashes_no_loop(self):
        state = LoopState(threshold=3)
        state.push("a")
        state.push("b")
        state.push("c")
        is_loop, _ = state.check()
        assert not is_loop

    def test_window_eviction(self):
        from collections import deque

        state = LoopState(threshold=3)
        state.hashes = deque(maxlen=5)
        # Fill with "old"
        for _ in range(5):
            state.push("old")
        # Now push different hashes to evict
        for i in range(5):
            state.push(f"new-{i}")
        is_loop, count = state.check()
        assert not is_loop
        assert count == 1


class TestBudgetState:
    def test_no_limit(self):
        state = BudgetState()
        state.add_cost(100.0)
        assert not state.exceeded
        assert state.remaining_usd is None

    def test_under_limit(self):
        state = BudgetState(limit_usd=10.0)
        state.add_cost(5.0)
        assert not state.exceeded
        assert state.remaining_usd == 5.0

    def test_at_limit(self):
        state = BudgetState(limit_usd=10.0)
        state.add_cost(10.0)
        assert state.exceeded
        assert state.remaining_usd == 0.0

    def test_over_limit(self):
        state = BudgetState(limit_usd=10.0)
        state.add_cost(15.0)
        assert state.exceeded
        assert state.remaining_usd == 0.0


class TestDetectLoop:
    def test_no_loop(self):
        is_loop, count = detect_loop(["a", "b", "c"], "d", threshold=3)
        assert not is_loop
        assert count == 1

    def test_loop_detected(self):
        is_loop, count = detect_loop(["x", "x"], "x", threshold=3)
        assert is_loop
        assert count == 3


class TestCheckBudget:
    def test_no_limit(self):
        exceeded, remaining = check_budget(100.0, None)
        assert not exceeded
        assert remaining is None

    def test_under(self):
        exceeded, remaining = check_budget(5.0, 10.0)
        assert not exceeded
        assert remaining == 5.0

    def test_exceeded(self):
        exceeded, remaining = check_budget(12.0, 10.0)
        assert exceeded
        assert remaining == 0.0
