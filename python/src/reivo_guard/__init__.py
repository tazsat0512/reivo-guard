"""reivo-guard — Open-source guardrails for AI agents."""

from .anomaly import AnomalyResult, EwmaState, detect_anomaly, update_ewma
from .callback import ReivoGuard
from .cosine import CosineLoopResult, detect_loop_by_cosine
from .cusum import CusumResult, CusumState, detect_drift, reset_cusum, update_cusum
from .degradation import DegradationLevel, DegradationPolicy, get_degradation_level
from .forecast import BudgetForecaster, CostSample, ForecastResult
from .guard import BudgetExceeded, LoopDetected, detect_loop, check_budget, hash_messages
from .sequence import SequenceLoopResult, detect_sequence_loop, detect_sequence_loop_ngram
from .standalone import (
    AnomalyDetected,
    Guard,
    GuardDecision,
    RateLimitExceeded,
    estimate_cost,
)

__all__ = [
    # Core
    "Guard",
    "GuardDecision",
    "estimate_cost",
    # Exceptions
    "BudgetExceeded",
    "LoopDetected",
    "AnomalyDetected",
    "RateLimitExceeded",
    # Anomaly detection
    "AnomalyResult",
    "EwmaState",
    "detect_anomaly",
    "update_ewma",
    # CUSUM drift detection
    "CusumResult",
    "CusumState",
    "detect_drift",
    "update_cusum",
    "reset_cusum",
    # Degradation
    "DegradationLevel",
    "DegradationPolicy",
    "get_degradation_level",
    # Budget forecasting
    "BudgetForecaster",
    "CostSample",
    "ForecastResult",
    # Loop detection
    "CosineLoopResult",
    "detect_loop",
    "detect_loop_by_cosine",
    "check_budget",
    "hash_messages",
    # Sequence pattern detection
    "SequenceLoopResult",
    "detect_sequence_loop",
    "detect_sequence_loop_ngram",
    # LiteLLM callback
    "ReivoGuard",
]

__version__ = "0.3.0"
