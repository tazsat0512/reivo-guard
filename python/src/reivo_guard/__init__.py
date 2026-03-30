"""reivo-guard — Open-source guardrails for AI agents."""

from .callback import ReivoGuard
from .cosine import CosineLoopResult, detect_loop_by_cosine
from .guard import BudgetExceeded, LoopDetected, detect_loop, check_budget, hash_messages
from .standalone import Guard, GuardDecision, estimate_cost

__all__ = [
    "Guard",
    "GuardDecision",
    "ReivoGuard",
    "BudgetExceeded",
    "LoopDetected",
    "CosineLoopResult",
    "detect_loop",
    "detect_loop_by_cosine",
    "check_budget",
    "hash_messages",
    "estimate_cost",
]

__version__ = "0.1.0"
