"""Portfolio optimization utilities for combining multiple strategies."""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.optimize import minimize


class PortfolioOptimizer:
    """Optimize portfolio weights across multiple strategies."""

    # Annualisation factor for daily returns (trading days)
    TRADING_DAYS = 252

    # ------------------------------------------------------------------ #
    #  Static / simple allocation methods                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def equal_weight(strategies: List[str]) -> Dict[str, float]:
        """Assign equal weight to each strategy.

        Args:
            strategies: List of strategy names.

        Returns:
            Dict mapping strategy name -> weight (sums to 1).
        """
        if not strategies:
            return {}
        w = 1.0 / len(strategies)
        return {s: w for s in strategies}

    # ------------------------------------------------------------------ #
    #  Optimisation-based methods                                          #
    # ------------------------------------------------------------------ #

    def max_sharpe(
        self, returns_df: pd.DataFrame, risk_free: float = 0.07
    ) -> Dict[str, float]:
        """Find portfolio weights that maximise the Sharpe ratio.

        Uses scipy.optimize.minimize with 'SLSQP' to minimise negative Sharpe.

        Args:
            returns_df: DataFrame of daily PnL per strategy.
            risk_free:  Annual risk-free rate (default 7% for Indian markets).

        Returns:
            Dict mapping strategy name -> weight (sums to 1).
        """
        strategies = list(returns_df.columns)
        n = len(strategies)

        if n == 0:
            return {}
        if n == 1:
            return {strategies[0]: 1.0}

        # Annualised statistics
        mu = returns_df.mean().values * self.TRADING_DAYS
        cov = returns_df.cov().values * self.TRADING_DAYS
        daily_rf = risk_free / self.TRADING_DAYS

        def neg_sharpe(w: np.ndarray) -> float:
            port_ret = float(w @ mu)
            port_var = float(w @ cov @ w)
            port_vol = np.sqrt(max(port_var, 1e-12))
            annual_rf = risk_free
            sharpe = (port_ret - annual_rf) / port_vol
            return -sharpe

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * n
        w0 = np.ones(n) / n

        result = minimize(
            neg_sharpe,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 500},
        )

        weights = result.x if result.success else w0
        weights = np.clip(weights, 0, 1)
        total = weights.sum()
        if total > 1e-10:
            weights /= total

        return dict(zip(strategies, weights.tolist()))

    def min_volatility(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Find the minimum variance portfolio weights.

        Args:
            returns_df: DataFrame of daily PnL per strategy.

        Returns:
            Dict mapping strategy name -> weight (sums to 1).
        """
        strategies = list(returns_df.columns)
        n = len(strategies)

        if n == 0:
            return {}
        if n == 1:
            return {strategies[0]: 1.0}

        cov = returns_df.cov().values

        def portfolio_variance(w: np.ndarray) -> float:
            return float(w @ cov @ w)

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(0.0, 1.0)] * n
        w0 = np.ones(n) / n

        result = minimize(
            portfolio_variance,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-9, "maxiter": 500},
        )

        weights = result.x if result.success else w0
        weights = np.clip(weights, 0, 1)
        total = weights.sum()
        if total > 1e-10:
            weights /= total

        return dict(zip(strategies, weights.tolist()))

    def risk_parity(self, returns_df: pd.DataFrame) -> Dict[str, float]:
        """Compute Equal Risk Contribution (risk parity) weights.

        Each strategy contributes equally to total portfolio risk.

        Args:
            returns_df: DataFrame of daily PnL per strategy.

        Returns:
            Dict mapping strategy name -> weight (sums to 1).
        """
        strategies = list(returns_df.columns)
        n = len(strategies)

        if n == 0:
            return {}
        if n == 1:
            return {strategies[0]: 1.0}

        cov = returns_df.cov().values
        target_contrib = np.ones(n) / n  # equal risk contribution

        def risk_parity_objective(w: np.ndarray) -> float:
            port_var = float(w @ cov @ w)
            port_vol = np.sqrt(max(port_var, 1e-12))
            # Marginal risk contributions
            marginal = cov @ w / port_vol
            risk_contrib = w * marginal
            # Minimise sum of squared deviations from target
            return float(np.sum((risk_contrib / risk_contrib.sum() - target_contrib) ** 2))

        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        bounds = [(1e-4, 1.0)] * n
        w0 = np.ones(n) / n

        result = minimize(
            risk_parity_objective,
            w0,
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"ftol": 1e-10, "maxiter": 1000},
        )

        weights = result.x if result.success else w0
        weights = np.clip(weights, 0, 1)
        total = weights.sum()
        if total > 1e-10:
            weights /= total

        return dict(zip(strategies, weights.tolist()))

    # ------------------------------------------------------------------ #
    #  Constraint application                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def apply_constraints(
        weights: Dict[str, float], max_per_strategy: float = 0.4
    ) -> Dict[str, float]:
        """Clip individual weights and renormalise to sum to 1.

        Uses iterative water-filling so that renormalisation does not push any
        previously-unconstrained weight above ``max_per_strategy``.

        Args:
            weights: Dict of strategy name -> weight.
            max_per_strategy: Maximum allowed weight per strategy. Default 0.4.

        Returns:
            Dict of clipped and renormalised weights.
        """
        if not weights:
            return {}

        keys = list(weights.keys())
        w = np.array([float(weights[k]) for k in keys], dtype=float)
        n = len(w)

        total = w.sum()
        if total < 1e-10:
            return {k: 1.0 / n for k in keys}

        # Normalise first to get proper fractions
        w = w / total

        # Iteratively clip weights that exceed max and redistribute surplus
        capped = np.zeros(n, dtype=bool)
        for _ in range(n + 1):
            exceeded = (~capped) & (w > max_per_strategy + 1e-12)
            if not exceeded.any():
                break
            # Pin exceeded weights to the cap
            capped |= exceeded
            w[exceeded] = max_per_strategy
            # Renormalise only the uncapped weights to absorb the remaining mass
            uncapped_mass = 1.0 - w[capped].sum()
            uncapped_idx = ~capped
            if uncapped_idx.any() and uncapped_mass > 1e-12:
                w[uncapped_idx] = w[uncapped_idx] / w[uncapped_idx].sum() * uncapped_mass
            else:
                break

        # Final safety renormalise
        s = w.sum()
        if s > 1e-10:
            w = w / s

        return dict(zip(keys, w.tolist()))

    # ------------------------------------------------------------------ #
    #  Portfolio backtest                                                  #
    # ------------------------------------------------------------------ #

    def backtest_portfolio(
        self, returns_df: pd.DataFrame, weights: Dict[str, float]
    ) -> Dict:
        """Apply weights to strategy daily PnL and compute portfolio metrics.

        Args:
            returns_df: DataFrame of daily PnL per strategy.
            weights:    Dict of strategy name -> weight.

        Returns:
            Dict with keys: equity_curve (pd.Series), sharpe, total_pnl,
            max_drawdown, annualised_return, annualised_vol.
        """
        if returns_df.empty or not weights:
            return {
                "equity_curve": pd.Series(dtype=float),
                "sharpe": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "annualised_return": 0.0,
                "annualised_vol": 0.0,
            }

        # Align weights with available strategies
        avail = [s for s in weights if s in returns_df.columns]
        if not avail:
            return {
                "equity_curve": pd.Series(dtype=float),
                "sharpe": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "annualised_return": 0.0,
                "annualised_vol": 0.0,
            }

        w_arr = np.array([weights[s] for s in avail])
        w_arr /= w_arr.sum()

        port_returns = returns_df[avail].values @ w_arr
        port_series = pd.Series(port_returns, index=returns_df.index)

        # Equity curve (cumulative PnL)
        equity_curve = port_series.cumsum()

        # Max drawdown
        running_max = equity_curve.cummax()
        drawdown = running_max - equity_curve
        max_dd = float(drawdown.max()) if len(drawdown) > 0 else 0.0

        # Sharpe ratio (annualised)
        mean_r = float(port_series.mean())
        std_r = float(port_series.std())
        sharpe = (mean_r / std_r * np.sqrt(self.TRADING_DAYS)) if std_r > 1e-10 else 0.0

        return {
            "equity_curve": equity_curve,
            "sharpe": round(sharpe, 4),
            "total_pnl": round(float(port_series.sum()), 2),
            "max_drawdown": round(max_dd, 2),
            "annualised_return": round(mean_r * self.TRADING_DAYS, 2),
            "annualised_vol": round(std_r * np.sqrt(self.TRADING_DAYS), 4),
        }

    # ------------------------------------------------------------------ #
    #  Comparison table                                                   #
    # ------------------------------------------------------------------ #

    def compare_allocation_methods(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """Compare all allocation methods on the same returns DataFrame.

        Methods: equal_weight, max_sharpe, min_volatility, risk_parity.

        Args:
            returns_df: DataFrame of daily PnL per strategy.

        Returns:
            DataFrame with one row per method and columns:
            Method, Total PnL, Sharpe, Max DD, Annualised Return, Annualised Vol.
        """
        strategies = list(returns_df.columns)

        methods = {
            "Equal Weight": self.equal_weight(strategies),
            "Max Sharpe": self.max_sharpe(returns_df),
            "Min Volatility": self.min_volatility(returns_df),
            "Risk Parity": self.risk_parity(returns_df),
        }

        rows = []
        for method_name, weights in methods.items():
            constrained = self.apply_constraints(weights)
            metrics = self.backtest_portfolio(returns_df, constrained)

            weight_str = ", ".join(
                f"{k}: {v:.1%}" for k, v in sorted(constrained.items(), key=lambda x: -x[1])
            )

            rows.append({
                "Method": method_name,
                "Total PnL": metrics["total_pnl"],
                "Sharpe": metrics["sharpe"],
                "Max DD": metrics["max_drawdown"],
                "Ann. Return": metrics["annualised_return"],
                "Ann. Vol": metrics["annualised_vol"],
                "Weights": weight_str,
            })

        return pd.DataFrame(rows).set_index("Method")
