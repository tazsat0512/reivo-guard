"""Sequence pattern (n-gram cycle) detection — pure Python, zero dependencies.

Detects cyclic patterns like A→B→C→A→B→C that simple hash-based
loop detection misses. Uses n-gram frequency analysis to find repeating
subsequences in the request history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SequenceLoopResult:
    """Result of sequence pattern detection."""

    is_loop: bool
    cycle_length: Optional[int] = None
    """Length of the detected cycle (e.g., 3 for A→B→C→A→B→C)."""
    repetitions: int = 0
    """Number of times the cycle has repeated."""
    pattern: Optional[list[str]] = None
    """The detected repeating pattern (list of hashes)."""


def detect_sequence_loop(
    hashes: list[str],
    min_cycle_length: int = 2,
    max_cycle_length: int = 10,
    min_repetitions: int = 3,
) -> SequenceLoopResult:
    """Detect repeating cycles in a sequence of prompt hashes.

    Checks if the last N*k elements form a repeating pattern of length N.
    For example, [A, B, C, A, B, C, A, B, C] has cycle_length=3, repetitions=3.

    Args:
        hashes: List of prompt hashes (most recent last).
        min_cycle_length: Minimum cycle length to check. Default 2.
        max_cycle_length: Maximum cycle length to check. Default 10.
        min_repetitions: Minimum repetitions to trigger. Default 3.

    Returns:
        SequenceLoopResult with cycle details.
    """
    n = len(hashes)

    if n < min_cycle_length * min_repetitions:
        return SequenceLoopResult(is_loop=False)

    # Try each cycle length, shortest first (detect earliest)
    for cycle_len in range(min_cycle_length, min(max_cycle_length, n // min_repetitions) + 1):
        # Extract the candidate pattern from the tail
        pattern = hashes[-cycle_len:]

        # Count how many times this pattern repeats going backwards
        reps = 1
        pos = n - cycle_len * 2

        while pos >= 0:
            window = hashes[pos : pos + cycle_len]
            if window == pattern:
                reps += 1
                pos -= cycle_len
            else:
                break

        if reps >= min_repetitions:
            return SequenceLoopResult(
                is_loop=True,
                cycle_length=cycle_len,
                repetitions=reps,
                pattern=pattern,
            )

    return SequenceLoopResult(is_loop=False)


def detect_sequence_loop_ngram(
    hashes: list[str],
    min_cycle_length: int = 2,
    max_cycle_length: int = 10,
    min_repetitions: int = 3,
) -> SequenceLoopResult:
    """Detect repeating cycles using n-gram frequency analysis.

    More robust than the suffix-matching approach — detects cycles
    even when they don't align perfectly with the end of the sequence.

    Scans the entire hash history for the most frequent n-gram and
    checks if it appears >= min_repetitions times.
    """
    n = len(hashes)

    if n < min_cycle_length * min_repetitions:
        return SequenceLoopResult(is_loop=False)

    best_result = SequenceLoopResult(is_loop=False)

    for gram_len in range(min_cycle_length, min(max_cycle_length, n // min_repetitions) + 1):
        # Count all n-grams of this length
        counts: dict[tuple[str, ...], int] = {}
        for i in range(n - gram_len + 1):
            gram = tuple(hashes[i : i + gram_len])
            counts[gram] = counts.get(gram, 0) + 1

        # Find the most frequent n-gram
        for gram, count in counts.items():
            if count >= min_repetitions:
                # Prefer shorter cycles (more concerning) and more repetitions
                if (
                    not best_result.is_loop
                    or count > best_result.repetitions
                    or (count == best_result.repetitions and gram_len < (best_result.cycle_length or 999))
                ):
                    best_result = SequenceLoopResult(
                        is_loop=True,
                        cycle_length=gram_len,
                        repetitions=count,
                        pattern=list(gram),
                    )

    return best_result
