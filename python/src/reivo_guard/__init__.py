"""reivo-guard — Open-source guardrails for AI agents."""

from .anomaly import AnomalyResult, EwmaState, detect_anomaly, update_ewma
from .callback import ReivoGuard
from .cosine import CosineLoopResult, detect_loop_by_cosine
from .degradation import DegradationLevel, DegradationPolicy, get_degradation_level
from .guard import BudgetExceeded, LoopDetected, detect_loop, check_budget, hash_messages
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
    # Degradation
    "DegradationLevel",
    "DegradationPolicy",
    "get_degradation_level",
    # Loop detection
    "CosineLoopResult",
    "detect_loop",
    "detect_loop_by_cosine",
    "check_budget",
    "hash_messages",
    # LiteLLM callback
    "ReivoGuard",
]

__version__ = "0.2.0"
