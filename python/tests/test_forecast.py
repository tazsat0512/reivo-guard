"""Tests for budget exhaustion forecasting."""

from reivo_guard.forecast import BudgetForecaster, ForecastResult, _ols, _t_critical


class TestOLS:
    def test_perfect_linear(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [0.0, 2.0, 4.0, 6.0, 8.0]
        slope, intercept, r_sq, se = _ols(xs, ys)
        assert abs(slope - 2.0) < 1e-10
        assert abs(intercept) < 1e-10
        assert abs(r_sq - 1.0) < 1e-10
        assert abs(se) < 1e-10

    def test_with_offset(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [10.0, 12.0, 14.0, 16.0, 18.0]
        slope, intercept, r_sq, _ = _ols(xs, ys)
        assert abs(slope - 2.0) < 1e-10
        assert abs(intercept - 10.0) < 1e-10
        assert abs(r_sq - 1.0) < 1e-10

    def test_noisy_data(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [0.1, 1.8, 4.2, 5.9, 8.1]
        slope, intercept, r_sq, se = _ols(xs, ys)
        assert 1.5 < slope < 2.5
        assert r_sq > 0.95
        assert se > 0

    def test_constant_y(self):
        xs = [0.0, 1.0, 2.0, 3.0, 4.0]
        ys = [5.0, 5.0, 5.0, 5.0, 5.0]
        slope, intercept, r_sq, _ = _ols(xs, ys)
        assert abs(slope) < 1e-10
        assert abs(intercept - 5.0) < 1e-10

    def test_single_point(self):
        slope, intercept, r_sq, se = _ols([1.0], [2.0])
        assert intercept == 2.0
        assert se == 0.0


class TestTCritical:
    def test_known_values(self):
        assert abs(_t_critical(1) - 12.706) < 0.001
        assert abs(_t_critical(10) - 2.228) < 0.001
        assert abs(_t_critical(100) - 1.984) < 0.001

    def test_large_df(self):
        assert abs(_t_critical(1000) - 1.96) < 0.001

    def test_interpolation(self):
        val = _t_critical(12)
        assert 2.131 < val < 2.228  # between df=10 and df=15

    def test_zero_df(self):
        assert _t_critical(0) == 12.706


class TestBudgetForecaster:
    def test_insufficient_samples(self):
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=5)
        for i in range(3):
            f.record(float(i * 10), timestamp=float(i))
        result = f.forecast()
        assert result.eta_seconds is None
        assert result.samples == 3

    def test_linear_cost_growth(self):
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=5)
        # Cost grows $10/sec, starting at $0
        for i in range(10):
            f.record(float(i * 10), timestamp=float(i))
        result = f.forecast()
        assert result.eta_seconds is not None
        # At t=9, cost=90. Rate=10/s. Budget=100. ETA ≈ 1s
        assert 0.5 < result.eta_seconds < 2.0
        assert abs(result.cost_rate_per_second - 10.0) < 0.5
        assert result.r_squared > 0.99

    def test_no_cost_increase(self):
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=5)
        for i in range(10):
            f.record(50.0, timestamp=float(i))
        result = f.forecast()
        assert result.eta_seconds is None  # No increasing trend

    def test_already_exceeded(self):
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=5)
        for i in range(10):
            f.record(float(90 + i * 5), timestamp=float(i))
        result = f.forecast()
        # Cost already at 135 at t=9, budget is 100
        assert result.eta_seconds == 0.0

    def test_confidence_intervals(self):
        f = BudgetForecaster(budget_limit_usd=1000.0, min_samples=5)
        for i in range(20):
            f.record(float(i * 10), timestamp=float(i))
        result = f.forecast()
        assert result.eta_seconds is not None
        assert result.ci_lower is not None
        assert result.ci_upper is not None
        # CI should bracket the point estimate
        assert result.ci_lower <= result.eta_seconds <= result.ci_upper

    def test_max_samples_window(self):
        f = BudgetForecaster(budget_limit_usd=1000.0, max_samples=5)
        for i in range(20):
            f.record(float(i * 10), timestamp=float(i))
        result = f.forecast()
        assert result.samples == 5

    def test_reset(self):
        f = BudgetForecaster(budget_limit_usd=100.0)
        for i in range(10):
            f.record(float(i * 10), timestamp=float(i))
        f.reset()
        result = f.forecast()
        assert result.samples == 0
        assert result.eta_seconds is None

    def test_decreasing_cost_rate(self):
        """Negative slope should return no exhaustion."""
        f = BudgetForecaster(budget_limit_usd=100.0, min_samples=5)
        for i in range(10):
            f.record(float(100 - i * 5), timestamp=float(i))
        result = f.forecast()
        assert result.eta_seconds is None
        assert result.cost_rate_per_second < 0
