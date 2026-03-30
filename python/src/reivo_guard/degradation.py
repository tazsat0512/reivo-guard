"""Budget degradation — graceful response to budget pressure.

Instead of hard-blocking at 100%, progressively restricts capabilities
as budget usage increases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DegradationLevel = Literal["normal", "aggressive", "new_sessions_only", "blocked"]

AGGRESSIVE_THRESHOLD = 0.80
NEW_SESSIONS_ONLY_THRESHOLD = 0.95
BLOCKED_THRESHOLD = 1.0


@dataclass
class DegradationPolicy:
    """Current degradation state."""

    level: DegradationLevel
    usage_ratio: float
    force_aggressive_routing: bool
    block_new_sessions: bool
    block_all: bool


def get_degradation_level(used_usd: float, limit_usd: float) -> DegradationPolicy:
    """Determine degradation level based on budget usage.

    <80%    → normal: no restrictions
    80-95%  → aggressive: force cheaper model routing
    95-100% → new_sessions_only: only existing sessions continue
    ≥100%   → blocked: all requests blocked
    """
    if limit_usd <= 0:
        return DegradationPolicy(
            level="blocked",
            usage_ratio=1.0,
            force_aggressive_routing=True,
            block_new_sessions=True,
            block_all=True,
        )

    ratio = used_usd / limit_usd

    if ratio >= BLOCKED_THRESHOLD:
        return DegradationPolicy(
            level="blocked",
            usage_ratio=ratio,
            force_aggressive_routing=True,
            block_new_sessions=True,
            block_all=True,
        )

    if ratio >= NEW_SESSIONS_ONLY_THRESHOLD:
        return DegradationPolicy(
            level="new_sessions_only",
            usage_ratio=ratio,
            force_aggressive_routing=True,
            block_new_sessions=True,
            block_all=False,
        )

    if ratio >= AGGRESSIVE_THRESHOLD:
        return DegradationPolicy(
            level="aggressive",
            usage_ratio=ratio,
            force_aggressive_routing=True,
            block_new_sessions=False,
            block_all=False,
        )

    return DegradationPolicy(
        level="normal",
        usage_ratio=ratio,
        force_aggressive_routing=False,
        block_new_sessions=False,
        block_all=False,
    )
