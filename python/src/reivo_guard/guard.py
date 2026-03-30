"""Core guardrail logic — pure Python, zero dependencies."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional


class BudgetExceeded(Exception):
    """Raised when cumulative cost exceeds the configured budget limit."""

    def __init__(self, used: float, limit: float):
        self.used = used
        self.limit = limit
        super().__init__(f"Budget exceeded: ${used:.4f} / ${limit:.2f}")


class LoopDetected(Exception):
    """Raised when repeated prompts are detected."""

    def __init__(self, match_count: int, window: int):
        self.match_count = match_count
        self.window = window
        super().__init__(
            f"Loop detected: {match_count} identical prompts in last {window} requests"
        )


def _hash_messages(messages: Any) -> str:
    """Hash a messages list into a stable SHA-256 hex digest."""
    try:
        normalized = json.dumps(messages, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        normalized = str(messages)
    return hashlib.sha256(normalized.encode()).hexdigest()


@dataclass
class LoopState:
    """Tracks prompt hashes for loop detection."""

    hashes: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    threshold: int = 3

    def push(self, prompt_hash: str) -> None:
        self.hashes.append(prompt_hash)

    def check(self) -> tuple[bool, int]:
        """Check if the most recent hash appears too many times."""
        if not self.hashes:
            return False, 0
        latest = self.hashes[-1]
        count = sum(1 for h in self.hashes if h == latest)
        return count >= self.threshold, count


@dataclass
class BudgetState:
    """Tracks cumulative cost."""

    used_usd: float = 0.0
    limit_usd: Optional[float] = None

    def add_cost(self, cost: float) -> None:
        import math

        if not math.isfinite(cost) or cost < 0:
            return
        self.used_usd += cost

    @property
    def exceeded(self) -> bool:
        if self.limit_usd is None:
            return False
        return self.used_usd >= self.limit_usd

    @property
    def remaining_usd(self) -> Optional[float]:
        if self.limit_usd is None:
            return None
        return max(0.0, self.limit_usd - self.used_usd)


def detect_loop(
    hashes: list[str],
    current_hash: str,
    threshold: int = 3,
) -> tuple[bool, int]:
    """Check if current_hash appears >= threshold times in hashes list.

    Returns (is_loop, match_count).
    """
    all_hashes = hashes + [current_hash]
    count = sum(1 for h in all_hashes if h == current_hash)
    return count >= threshold, count


def check_budget(
    used_usd: float,
    limit_usd: Optional[float],
) -> tuple[bool, Optional[float]]:
    """Check if budget is exceeded.

    Returns (exceeded, remaining_usd). remaining is None if no limit set.
    """
    if limit_usd is None:
        return False, None
    remaining = max(0.0, limit_usd - used_usd)
    return used_usd >= limit_usd, remaining


def hash_messages(messages: Any) -> str:
    """Public interface for hashing messages."""
    return _hash_messages(messages)
