"""EWMA anomaly detection — pure Python, zero dependencies.

Detects unusual spikes in token consumption or cost using
Exponentially Weighted Moving Average with z-score thresholding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

EWMA_ALPHA = 0.3
ANOMALY_Z_THRESHOLD = 3.0


@dataclass
class EwmaState:
    """Running EWMA statistics."""

    ewma_value: float = 0.0
    ewma_variance: float = 0.0
    sample_count: int = 0


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""

    is_anomaly: bool
    z_score: float
    ewma_value: float
    current_rate: float


def detect_anomaly(
    state: EwmaState,
    current_rate: float,
    z_threshold: float = ANOMALY_Z_THRESHOLD,
    warmup: int = 5,
) -> AnomalyResult:
    """Detect if current_rate is anomalous given EWMA state.

    IMPORTANT: Call this BEFORE update_ewma() to detect spikes
    before the variance absorbs them.

    Args:
        state: Current EWMA state.
        current_rate: New observation (e.g., token count).
        z_threshold: Z-score threshold for anomaly. Default 3.0.
        warmup: Minimum samples before detecting. Default 5.
    """
    if state.sample_count < warmup:
        return AnomalyResult(
            is_anomaly=False,
            z_score=0.0,
            ewma_value=state.ewma_value,
            current_rate=current_rate,
        )

    std_dev = math.sqrt(state.ewma_variance)
    z_score = 0.0 if std_dev == 0 else abs(current_rate - state.ewma_value) / std_dev

    return AnomalyResult(
        is_anomaly=z_score > z_threshold,
        z_score=z_score,
        ewma_value=state.ewma_value,
        current_rate=current_rate,
    )


def update_ewma(
    state: EwmaState,
    new_value: float,
    alpha: float = EWMA_ALPHA,
) -> EwmaState:
    """Update EWMA state with a new observation."""
    diff = new_value - state.ewma_value
    new_ewma = state.ewma_value + alpha * diff
    new_variance = (1 - alpha) * (state.ewma_variance + alpha * diff * diff)

    return EwmaState(
        ewma_value=new_ewma,
        ewma_variance=new_variance,
        sample_count=state.sample_count + 1,
    )
