"""Tests for portfolio and correlation analysis modules."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research.correlation import (
    compute_strategy_returns,
    correlation_matrix,
    diversification_score,
    find_uncorrelated_pairs,
    marginal_contribution_to_risk,
)
from src.research.portfolio import PortfolioOptimizer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def synthetic_returns() -> pd.DataFrame:
    """Generate a realistic synthetic returns DataFrame with 4 strategies."""
    np.random.seed(0)
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="B")

    # Strategy 1: trending
    s1 = np.random.randn(n) * 100 + 5
    # Strategy 2: somewhat correlated with s1
    s2 = 0.5 * s1 + np.random.randn(n) * 80
    # Strategy 3: uncorrelated
    s3 = np.random.randn(n) * 90 - 2
    # Strategy 4: anti-correlated with s1
    s4 = -0.4 * s1 + np.random.randn(n) * 120

    df = pd.DataFrame(
        {"momentum_breakout": s1, "mean_reversion": s2, "orb_strategy": s3, "vwap_reversion": s4},
        index=dates,
    )
    return df


@pytest.fixture
def optimizer() -> PortfolioOptimizer:
    return PortfolioOptimizer()


# ---------------------------------------------------------------------------
# correlation.py tests
# ---------------------------------------------------------------------------

class TestCorrelationMatrix:
    def test_correlation_matrix_shape(self, synthetic_returns):
        """Correlation matrix must be square with same labels as input."""
        corr = correlation_matrix(synthetic_returns)
        n = synthetic_returns.shape[1]
        assert corr.shape == (n, n), f"Expected ({n}, {n}), got {corr.shape}"
        assert list(corr.columns) == list(synthetic_returns.columns)
        assert list(corr.index) == list(synthetic_returns.columns)

    def test_correlation_matrix_diagonal_is_one(self, synthetic_returns):
        """Diagonal entries must be 1.0."""
        corr = correlation_matrix(synthetic_returns)
        np.testing.assert_allclose(np.diag(corr.values), 1.0, atol=1e-6)

    def test_correlation_matrix_range(self, synthetic_returns):
        """All values must lie in [-1, 1]."""
        corr = correlation_matrix(synthetic_returns)
        assert corr.values.min() >= -1.0 - 1e-6
        assert corr.values.max() <= 1.0 + 1e-6

    def test_correlation_matrix_symmetry(self, synthetic_returns):
        """Matrix must be symmetric."""
        corr = correlation_matrix(synthetic_returns)
        np.testing.assert_allclose(corr.values, corr.values.T, atol=1e-8)

    def test_correlation_matrix_empty_input(self):
        """Empty DataFrame returns empty correlation matrix."""
        corr = correlation_matrix(pd.DataFrame())
        assert corr.empty

    def test_correlation_matrix_single_column(self):
        """Single-column DataFrame (no pairs) returns empty or 1x1 matrix."""
        df = pd.DataFrame({"only": np.random.randn(50)})
        corr = correlation_matrix(df)
        # Either empty or a 1x1 matrix; the key constraint is no crash
        assert isinstance(corr, pd.DataFrame)


class TestComputeStrategyReturns:
    def test_compute_strategy_returns_basic(self):
        """compute_strategy_returns should produce a DataFrame with correct columns."""
        class _FakeResult:
            def __init__(self, trades):
                self.trades = trades

        trades_a = [
            {"exit_date": "2024-01-02", "net_pnl": 100.0},
            {"exit_date": "2024-01-03", "net_pnl": -50.0},
        ]
        trades_b = [
            {"exit_date": "2024-01-02", "net_pnl": 200.0},
        ]
        results = {
            "strategy_a": _FakeResult(trades_a),
            "strategy_b": _FakeResult(trades_b),
        }
        df = compute_strategy_returns(results)
        assert "strategy_a" in df.columns
        assert "strategy_b" in df.columns
        assert df["strategy_a"].sum() == pytest.approx(50.0)
        assert df["strategy_b"].sum() == pytest.approx(200.0)

    def test_compute_strategy_returns_empty_trades(self):
        """Empty trades should produce a zero-column or empty DataFrame without error."""
        class _R:
            trades = []
        results = {"empty": _R()}
        df = compute_strategy_returns(results)
        assert isinstance(df, pd.DataFrame)


# ---------------------------------------------------------------------------
# portfolio.py tests
# ---------------------------------------------------------------------------

class TestEqualWeight:
    def test_equal_weights_sum_to_one(self, optimizer):
        """Equal weights must sum exactly to 1."""
        strategies = ["a", "b", "c", "d"]
        weights = optimizer.equal_weight(strategies)
        assert pytest.approx(sum(weights.values()), abs=1e-9) == 1.0

    def test_equal_weights_all_equal(self, optimizer):
        """Each weight must equal 1/n."""
        strategies = ["x", "y", "z"]
        weights = optimizer.equal_weight(strategies)
        expected = 1.0 / 3.0
        for w in weights.values():
            assert pytest.approx(w, abs=1e-9) == expected

    def test_equal_weights_empty(self, optimizer):
        """Empty strategy list returns empty dict."""
        assert optimizer.equal_weight([]) == {}

    def test_equal_weights_single(self, optimizer):
        """Single strategy gets weight 1.0."""
        weights = optimizer.equal_weight(["solo"])
        assert weights == {"solo": pytest.approx(1.0)}


class TestMaxSharpe:
    def test_max_sharpe_weights_valid(self, optimizer, synthetic_returns):
        """Max Sharpe weights must sum to 1 and all be in [0, 1]."""
        weights = optimizer.max_sharpe(synthetic_returns)
        assert set(weights.keys()) == set(synthetic_returns.columns)
        total = sum(weights.values())
        assert pytest.approx(total, abs=1e-6) == 1.0
        for w in weights.values():
            assert -1e-9 <= w <= 1.0 + 1e-9

    def test_max_sharpe_single_strategy(self, optimizer):
        """Single-strategy DataFrame: weight should be 1.0."""
        df = pd.DataFrame({"only": np.random.randn(100) * 10})
        weights = optimizer.max_sharpe(df)
        assert pytest.approx(weights["only"], abs=1e-6) == 1.0

    def test_max_sharpe_returns_dict(self, optimizer, synthetic_returns):
        """Return type must be dict."""
        weights = optimizer.max_sharpe(synthetic_returns)
        assert isinstance(weights, dict)


class TestMinVolatility:
    def test_min_volatility_weights_valid(self, optimizer, synthetic_returns):
        """Min volatility weights must sum to 1 and all be in [0, 1]."""
        weights = optimizer.min_volatility(synthetic_returns)
        assert set(weights.keys()) == set(synthetic_returns.columns)
        total = sum(weights.values())
        assert pytest.approx(total, abs=1e-6) == 1.0
        for w in weights.values():
            assert -1e-9 <= w <= 1.0 + 1e-9


class TestRiskParity:
    def test_risk_parity_weights_valid(self, optimizer, synthetic_returns):
        """Risk parity weights must be positive and sum to 1."""
        weights = optimizer.risk_parity(synthetic_returns)
        assert set(weights.keys()) == set(synthetic_returns.columns)
        total = sum(weights.values())
        assert pytest.approx(total, abs=1e-4) == 1.0
        for w in weights.values():
            assert w >= -1e-6  # non-negative

    def test_risk_parity_single_strategy(self, optimizer):
        """Single-strategy DataFrame: weight should be 1.0."""
        df = pd.DataFrame({"only": np.random.randn(100) * 10})
        weights = optimizer.risk_parity(df)
        assert pytest.approx(weights["only"], abs=1e-6) == 1.0

    def test_risk_parity_returns_dict(self, optimizer, synthetic_returns):
        """Return type must be dict."""
        weights = optimizer.risk_parity(synthetic_returns)
        assert isinstance(weights, dict)


class TestApplyConstraints:
    def test_apply_constraints_clips_and_renormalises(self, optimizer):
        """Weights above max_per_strategy should be clipped; result sums to 1."""
        weights = {"a": 0.8, "b": 0.1, "c": 0.1}
        result = optimizer.apply_constraints(weights, max_per_strategy=0.4)
        for w in result.values():
            assert w <= 0.4 + 1e-9
        assert pytest.approx(sum(result.values()), abs=1e-9) == 1.0

    def test_apply_constraints_sum_to_one(self, optimizer):
        """apply_constraints output always sums to 1."""
        weights = {"x": 0.5, "y": 0.3, "z": 0.2}
        result = optimizer.apply_constraints(weights, max_per_strategy=0.4)
        assert pytest.approx(sum(result.values()), abs=1e-9) == 1.0


# ---------------------------------------------------------------------------
# Diversification score tests
# ---------------------------------------------------------------------------

class TestDiversificationScore:
    def test_diversification_score_range(self, synthetic_returns):
        """Diversification score must be in [0, 1]."""
        score = diversification_score(synthetic_returns)
        assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_diversification_score_perfect(self):
        """Uncorrelated strategies should yield a high diversification score."""
        np.random.seed(1)
        n = 200
        df = pd.DataFrame(
            {
                "s1": np.random.randn(n),
                "s2": np.random.randn(n),
                "s3": np.random.randn(n),
            }
        )
        score = diversification_score(df)
        # With independent normals the score should be > 0.7
        assert score > 0.7, f"Expected high score for uncorrelated strategies, got {score}"

    def test_diversification_score_identical(self):
        """Identical strategies should yield a low diversification score."""
        np.random.seed(2)
        base = np.random.randn(200)
        df = pd.DataFrame({"s1": base, "s2": base, "s3": base})
        score = diversification_score(df)
        # Perfectly correlated should be close to 0
        assert score < 0.1, f"Expected low score for identical strategies, got {score}"

    def test_diversification_score_single_column(self):
        """Single strategy: no off-diagonal correlations -> returns 1.0."""
        df = pd.DataFrame({"only": np.random.randn(100)})
        score = diversification_score(df)
        assert score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Marginal contribution to risk
# ---------------------------------------------------------------------------

class TestMarginalContributionToRisk:
    def test_marginal_contribution_sums_to_portfolio_vol(self, synthetic_returns):
        """Sum of risk contributions must equal portfolio volatility."""
        optimizer = PortfolioOptimizer()
        strategies = list(synthetic_returns.columns)
        weights_dict = optimizer.equal_weight(strategies)
        w = np.array([weights_dict[s] for s in strategies])
        cov = synthetic_returns.cov()

        contrib = marginal_contribution_to_risk(w, cov)
        port_vol = np.sqrt(float(w @ cov.values @ w))
        assert pytest.approx(float(contrib.sum()), abs=1e-6) == port_vol


# ---------------------------------------------------------------------------
# Backtest portfolio
# ---------------------------------------------------------------------------

class TestBacktestPortfolio:
    def test_backtest_portfolio_returns_dict(self, optimizer, synthetic_returns):
        """backtest_portfolio must return a dict with expected keys."""
        strategies = list(synthetic_returns.columns)
        weights = optimizer.equal_weight(strategies)
        result = optimizer.backtest_portfolio(synthetic_returns, weights)
        for key in ("equity_curve", "sharpe", "total_pnl", "max_drawdown"):
            assert key in result, f"Missing key: {key}"

    def test_backtest_portfolio_equity_curve_length(self, optimizer, synthetic_returns):
        """Equity curve length must match the number of dates in returns_df."""
        weights = optimizer.equal_weight(list(synthetic_returns.columns))
        result = optimizer.backtest_portfolio(synthetic_returns, weights)
        assert len(result["equity_curve"]) == len(synthetic_returns)


# ---------------------------------------------------------------------------
# Find uncorrelated pairs
# ---------------------------------------------------------------------------

class TestFindUncorrelatedPairs:
    def test_find_uncorrelated_pairs_returns_list(self, synthetic_returns):
        """Must return a list of tuples."""
        corr = correlation_matrix(synthetic_returns)
        pairs = find_uncorrelated_pairs(corr, threshold=0.3)
        assert isinstance(pairs, list)
        for pair in pairs:
            assert len(pair) == 2

    def test_find_uncorrelated_pairs_respects_threshold(self, synthetic_returns):
        """All returned pairs must satisfy |corr| <= threshold."""
        corr = correlation_matrix(synthetic_returns)
        threshold = 0.3
        pairs = find_uncorrelated_pairs(corr, threshold=threshold)
        for a, b in pairs:
            assert abs(corr.loc[a, b]) <= threshold + 1e-9

    def test_find_uncorrelated_pairs_empty_matrix(self):
        """Empty correlation matrix should return empty list."""
        pairs = find_uncorrelated_pairs(pd.DataFrame(), threshold=0.3)
        assert pairs == []
