"""Budget exhaustion forecasting — linear regression with confidence intervals.

Predicts when the budget will be exhausted based on recent cost history.
Uses ordinary least squares with t-distribution confidence intervals.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ForecastResult:
    """Budget exhaustion forecast."""

    eta_seconds: Optional[float]
    """Estimated seconds until budget exhaustion. None if not enough data or no trend."""
    ci_lower: Optional[float]
    """Lower bound of 95% CI (seconds). None if unavailable."""
    ci_upper: Optional[float]
    """Upper bound of 95% CI (seconds). None if unavailable."""
    cost_rate_per_second: float
    """Current cost rate (USD/second) from regression slope."""
    r_squared: float
    """R² goodness of fit. Low R² means high uncertainty."""
    samples: int
    """Number of data points used."""


@dataclass
class CostSample:
    """A single cost observation."""

    timestamp: float
    cumulative_cost: float


class BudgetForecaster:
    """Forecasts budget exhaustion using linear regression on cumulative cost.

    Args:
        budget_limit_usd: Total budget limit.
        min_samples: Minimum samples before forecasting. Default 5.
        max_samples: Maximum samples to retain (sliding window). Default 100.
    """

    def __init__(
        self,
        budget_limit_usd: float,
        min_samples: int = 5,
        max_samples: int = 100,
    ) -> None:
        self._limit = budget_limit_usd
        self._min_samples = min_samples
        self._max_samples = max_samples
        self._samples: list[CostSample] = []

    def record(self, cumulative_cost: float, timestamp: Optional[float] = None) -> None:
        """Record a cost observation."""
        ts = timestamp if timestamp is not None else time.monotonic()
        self._samples.append(CostSample(timestamp=ts, cumulative_cost=cumulative_cost))
        if len(self._samples) > self._max_samples:
            self._samples = self._samples[-self._max_samples :]

    def forecast(self) -> ForecastResult:
        """Predict budget exhaustion time.

        Uses OLS linear regression: cost = slope * time + intercept
        Then solves for time when cost = budget_limit.
        """
        n = len(self._samples)

        if n < self._min_samples:
            return ForecastResult(
                eta_seconds=None,
                ci_lower=None,
                ci_upper=None,
                cost_rate_per_second=0.0,
                r_squared=0.0,
                samples=n,
            )

        # Normalize timestamps to avoid floating point issues
        t0 = self._samples[0].timestamp
        xs = [s.timestamp - t0 for s in self._samples]
        ys = [s.cumulative_cost for s in self._samples]

        # OLS: y = slope * x + intercept
        slope, intercept, r_sq, se_slope = _ols(xs, ys)

        if slope <= 0:
            # Cost not increasing — no exhaustion predicted
            return ForecastResult(
                eta_seconds=None,
                ci_lower=None,
                ci_upper=None,
                cost_rate_per_second=slope,
                r_squared=r_sq,
                samples=n,
            )

        # Time when cost reaches limit: limit = slope * t + intercept
        # t = (limit - intercept) / slope
        now = self._samples[-1].timestamp - t0
        t_exhaust = (self._limit - intercept) / slope
        eta = t_exhaust - now

        if eta <= 0:
            return ForecastResult(
                eta_seconds=0.0,
                ci_lower=0.0,
                ci_upper=0.0,
                cost_rate_per_second=slope,
                r_squared=r_sq,
                samples=n,
            )

        # 95% CI on slope using t-distribution approximation
        # For n >= 5, t_0.025 ≈ 2.0 (conservative)
        t_crit = _t_critical(n - 2)
        slope_lower = slope - t_crit * se_slope
        slope_upper = slope + t_crit * se_slope

        ci_lower: Optional[float] = None
        ci_upper: Optional[float] = None

        if slope_upper > 0:
            t_fast = (self._limit - intercept) / slope_upper
            ci_lower = max(0, t_fast - now)

        if slope_lower > 0:
            t_slow = (self._limit - intercept) / slope_lower
            ci_upper = max(0, t_slow - now)

        return ForecastResult(
            eta_seconds=max(0, eta),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            cost_rate_per_second=slope,
            r_squared=r_sq,
            samples=n,
        )

    def reset(self) -> None:
        """Clear all samples."""
        self._samples.clear()


def _ols(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float, float]:
    """Ordinary least squares regression.

    Returns (slope, intercept, r_squared, standard_error_of_slope).
    """
    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xx = sum(x * x for x in xs)
    sum_xy = sum(x * y for x, y in zip(xs, ys))

    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return 0.0, sum_y / n if n > 0 else 0.0, 0.0, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R²
    mean_y = sum_y / n
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r_sq = max(0.0, 1 - (ss_res / ss_tot)) if ss_tot > 0 else 0.0

    # Standard error of slope
    if n <= 2 or denom == 0:
        se_slope = 0.0
    else:
        mse = ss_res / (n - 2)
        se_slope = math.sqrt(mse / (sum_xx - sum_x * sum_x / n)) if (sum_xx - sum_x * sum_x / n) > 0 else 0.0

    return slope, intercept, r_sq, se_slope


def _t_critical(df: int) -> float:
    """Approximate t-critical value for 95% CI (two-tailed).

    Uses a lookup + interpolation for small df, converges to 1.96.
    """
    # Pre-computed t_0.025 for small degrees of freedom
    table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
        6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
        15: 2.131, 20: 2.086, 30: 2.042, 50: 2.009, 100: 1.984,
    }
    if df <= 0:
        return 12.706
    if df in table:
        return table[df]
    if df > 100:
        return 1.96

    # Linear interpolation between known values
    keys = sorted(table.keys())
    for i in range(len(keys) - 1):
        if keys[i] <= df <= keys[i + 1]:
            lo, hi = keys[i], keys[i + 1]
            frac = (df - lo) / (hi - lo)
            return table[lo] + frac * (table[hi] - table[lo])

    return 1.96
