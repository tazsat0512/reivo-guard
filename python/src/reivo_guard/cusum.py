"""CUSUM (Cumulative Sum) change point detection — pure Python, zero dependencies.

Detects gradual drift in metrics that EWMA might miss.
For example: token consumption slowly increasing 5% per request.

Uses the Page's CUSUM algorithm with automatic threshold estimation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class CusumState:
    """Running CUSUM state."""

    pos_sum: float = 0.0
    """Cumulative positive deviations from target."""
    neg_sum: float = 0.0
    """Cumulative negative deviations from target."""
    target: float = 0.0
    """Expected value (running mean)."""
    sample_count: int = 0
    """Number of observations."""
    sum_values: float = 0.0
    """Sum of all values (for running mean)."""
    sum_sq_values: float = 0.0
    """Sum of squared values (for running variance)."""


@dataclass
class CusumResult:
    """Result of CUSUM change point detection."""

    drift_detected: bool
    direction: Optional[str] = None
    """'up' or 'down' — direction of detected drift."""
    cusum_value: float = 0.0
    """Current CUSUM value that triggered (positive or negative sum)."""
    threshold: float = 0.0
    """The threshold that was exceeded."""
    deviation_from_target: float = 0.0
    """How far the current value is from the running target."""


def detect_drift(
    state: CusumState,
    current_value: float,
    threshold: Optional[float] = None,
    slack: Optional[float] = None,
    warmup: int = 10,
) -> CusumResult:
    """Detect gradual drift using CUSUM.

    Call this BEFORE update_cusum().

    Args:
        state: Current CUSUM state.
        current_value: New observation.
        threshold: Decision threshold. Default: 4 * std_dev (auto-calculated).
        slack: Allowable slack (drift tolerance). Default: 0.5 * std_dev.
        warmup: Minimum samples before detecting. Default 10.

    Returns:
        CusumResult indicating if drift is detected.
    """
    if state.sample_count < warmup:
        return CusumResult(
            drift_detected=False,
            deviation_from_target=current_value - state.target if state.sample_count > 0 else 0.0,
        )

    std_dev = _running_std(state)
    if std_dev == 0:
        std_dev = abs(state.target) * 0.01 or 1.0  # fallback

    h = threshold if threshold is not None else 4.0 * std_dev
    k = slack if slack is not None else 0.5 * std_dev

    deviation = current_value - state.target

    # CUSUM update (preview — actual state update in update_cusum)
    new_pos = max(0, state.pos_sum + deviation - k)
    new_neg = max(0, state.neg_sum - deviation - k)

    if new_pos > h:
        return CusumResult(
            drift_detected=True,
            direction="up",
            cusum_value=new_pos,
            threshold=h,
            deviation_from_target=deviation,
        )

    if new_neg > h:
        return CusumResult(
            drift_detected=True,
            direction="down",
            cusum_value=new_neg,
            threshold=h,
            deviation_from_target=deviation,
        )

    return CusumResult(
        drift_detected=False,
        cusum_value=max(new_pos, new_neg),
        threshold=h,
        deviation_from_target=deviation,
    )


def update_cusum(
    state: CusumState,
    new_value: float,
    slack: Optional[float] = None,
) -> CusumState:
    """Update CUSUM state with a new observation.

    Args:
        state: Current state.
        new_value: New observation.
        slack: Allowable slack. Default: 0.5 * std_dev (auto).
    """
    new_count = state.sample_count + 1
    new_sum = state.sum_values + new_value
    new_sum_sq = state.sum_sq_values + new_value * new_value
    new_target = new_sum / new_count

    # Use previous target for CUSUM calculation (not updated target)
    deviation = new_value - state.target if state.sample_count > 0 else 0.0

    std_dev = _running_std(state)
    k = slack if slack is not None else 0.5 * (std_dev if std_dev > 0 else 1.0)

    new_pos = max(0, state.pos_sum + deviation - k)
    new_neg = max(0, state.neg_sum - deviation - k)

    return CusumState(
        pos_sum=new_pos,
        neg_sum=new_neg,
        target=new_target,
        sample_count=new_count,
        sum_values=new_sum,
        sum_sq_values=new_sum_sq,
    )


def reset_cusum(state: CusumState) -> CusumState:
    """Reset CUSUM sums but keep the running statistics.

    Call after a drift is detected and handled, to start fresh detection
    while preserving the learned target and variance.
    """
    return CusumState(
        pos_sum=0.0,
        neg_sum=0.0,
        target=state.target,
        sample_count=state.sample_count,
        sum_values=state.sum_values,
        sum_sq_values=state.sum_sq_values,
    )


def _running_std(state: CusumState) -> float:
    """Calculate running standard deviation from state."""
    if state.sample_count < 2:
        return 0.0
    mean = state.sum_values / state.sample_count
    variance = (state.sum_sq_values / state.sample_count) - mean * mean
    return math.sqrt(max(0, variance))
