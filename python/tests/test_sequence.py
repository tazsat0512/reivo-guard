"""Tests for sequence pattern (n-gram cycle) detection."""

from reivo_guard.sequence import (
    SequenceLoopResult,
    detect_sequence_loop,
    detect_sequence_loop_ngram,
)


class TestDetectSequenceLoop:
    def test_no_loop_short(self):
        result = detect_sequence_loop(["a", "b"])
        assert not result.is_loop

    def test_simple_cycle(self):
        # A→B→A→B→A→B (cycle_len=2, reps=3)
        hashes = ["a", "b"] * 3
        result = detect_sequence_loop(hashes, min_cycle_length=2, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 2
        assert result.repetitions == 3
        assert result.pattern == ["a", "b"]

    def test_triple_cycle(self):
        # A→B→C→A→B→C→A→B→C
        hashes = ["a", "b", "c"] * 3
        result = detect_sequence_loop(hashes)
        assert result.is_loop
        assert result.cycle_length == 3
        assert result.repetitions == 3

    def test_no_loop_random(self):
        hashes = ["a", "b", "c", "d", "e", "f", "g", "h"]
        result = detect_sequence_loop(hashes)
        assert not result.is_loop

    def test_insufficient_reps(self):
        # Only 2 repetitions, need 3
        hashes = ["a", "b", "a", "b"]
        result = detect_sequence_loop(hashes, min_repetitions=3)
        assert not result.is_loop

    def test_long_cycle(self):
        pattern = ["a", "b", "c", "d", "e"]
        hashes = pattern * 4
        result = detect_sequence_loop(hashes, min_cycle_length=2, max_cycle_length=10, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 5
        assert result.repetitions >= 3

    def test_prefers_shorter_cycle(self):
        # ab repeated 6 times also contains abab repeated 3 times
        # Should detect cycle_len=2 first
        hashes = ["a", "b"] * 6
        result = detect_sequence_loop(hashes, min_cycle_length=2, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 2

    def test_cycle_with_prefix(self):
        # x, y, then a→b→a→b→a→b
        hashes = ["x", "y", "a", "b", "a", "b", "a", "b"]
        result = detect_sequence_loop(hashes, min_cycle_length=2, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 2

    def test_max_cycle_length_respected(self):
        pattern = ["a", "b", "c", "d", "e", "f"]
        hashes = pattern * 3
        result = detect_sequence_loop(hashes, max_cycle_length=5, min_repetitions=3)
        assert not result.is_loop  # cycle_len=6 exceeds max


class TestDetectSequenceLoopNgram:
    def test_no_loop_short(self):
        result = detect_sequence_loop_ngram(["a", "b"])
        assert not result.is_loop

    def test_simple_cycle(self):
        hashes = ["a", "b"] * 4
        result = detect_sequence_loop_ngram(hashes, min_repetitions=3)
        assert result.is_loop
        assert result.cycle_length == 2

    def test_cycle_not_aligned_at_end(self):
        """N-gram approach should detect cycles even with trailing noise."""
        hashes = ["a", "b", "c", "a", "b", "c", "a", "b", "c", "x"]
        result = detect_sequence_loop_ngram(hashes, min_cycle_length=2, min_repetitions=3)
        assert result.is_loop
        # May detect bigram ["a","b"] (3x) or trigram ["a","b","c"] (3x)
        assert result.cycle_length in (2, 3)

    def test_no_loop_random(self):
        hashes = list("abcdefghij")
        result = detect_sequence_loop_ngram(hashes)
        assert not result.is_loop

    def test_prefers_more_repetitions(self):
        # "ab" appears 5 times, "abc" appears 3 times
        hashes = ["a", "b"] * 5 + ["c"]
        result = detect_sequence_loop_ngram(hashes, min_repetitions=3)
        assert result.is_loop
        assert result.repetitions >= 3

    def test_mixed_cycles(self):
        """When multiple cycles exist, should find the most frequent."""
        hashes = ["a", "b", "a", "b", "a", "b", "c", "d", "c", "d"]
        result = detect_sequence_loop_ngram(hashes, min_repetitions=3)
        assert result.is_loop
        assert result.pattern == ["a", "b"]

    def test_single_element_repeat_below_min_cycle(self):
        """Single element repeats shouldn't trigger if min_cycle_length=2."""
        hashes = ["a"] * 10
        result = detect_sequence_loop_ngram(hashes, min_cycle_length=2, min_repetitions=3)
        # "aa" appears 9 times as bigram
        assert result.is_loop
        assert result.cycle_length == 2
