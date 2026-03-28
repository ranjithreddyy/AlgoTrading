"""Regime-conditional strategy selection.

Learns which strategies perform best within each volatility regime and
provides a regime -> [strategy] mapping for live allocation.
"""

from typing import Dict, List, Optional, Type

import numpy as np
import pandas as pd

from src.features.regime_features import vol_regime
from src.backtests.engine import BacktestEngine
from src.strategies.base import Strategy, StrategyConfig


# Human-readable regime labels
REGIME_LABELS = {
    0: "low_vol",
    1: "normal_vol",
    2: "high_vol",
    3: "extreme_vol",
}


class RegimeStrategySelector:
    """Learn and apply regime-conditional strategy allocation.

    For each volatility regime (low / normal / high / extreme) this class
    backtests every strategy independently on the data slices that fall within
    that regime, ranks strategies by Sharpe ratio, and exposes a
    ``select_strategies`` method for inference time.

    Args:
        strategies: List of (strategy_class, StrategyConfig) tuples.
        regime_feature: Name of the regime column to use.  Currently only
            'vol_regime' is supported (computed via regime_features.vol_regime).
    """

    def __init__(
        self,
        strategies: List[tuple],
        regime_feature: str = "vol_regime",
    ):
        self.strategies = strategies  # [(cls, config), ...]
        self.regime_feature = regime_feature

        # Populated by fit()
        self._regime_rankings: Dict[int, List[str]] = {}
        self._regime_metrics: Dict[int, pd.DataFrame] = {}
        self._is_fitted: bool = False

    # ------------------------------------------------------------------ #
    #  fit                                                                 #
    # ------------------------------------------------------------------ #

    def fit(self, df: pd.DataFrame) -> "RegimeStrategySelector":
        """Learn which strategies perform best in each regime.

        Args:
            df: OHLCV DataFrame with columns: date, open, high, low, close, volume.
                Must have enough rows for the regime feature to be computed
                (at least ~130 rows for default vol_regime parameters).

        Returns:
            self (for chaining).
        """
        work = df.copy()
        if "date" not in work.columns:
            work = work.reset_index()

        # Compute regime labels
        regimes = vol_regime(work)
        work[self.regime_feature] = regimes.values

        # Drop NaN regime rows
        work = work.dropna(subset=[self.regime_feature]).reset_index(drop=True)

        unique_regimes = sorted(work[self.regime_feature].dropna().unique())

        engine = BacktestEngine()
        self._regime_rankings = {}
        self._regime_metrics = {}

        for regime_id in unique_regimes:
            regime_id = int(regime_id)
            slice_df = work[work[self.regime_feature] == regime_id].copy()

            if len(slice_df) < 5:
                # Not enough data for this regime – skip
                continue

            rows = []
            for cls, config in self.strategies:
                try:
                    strategy = cls(config)
                    result = engine.run(strategy, slice_df)
                    rows.append(
                        {
                            "strategy": config.name,
                            "sharpe": result.sharpe_ratio,
                            "net_pnl": result.net_pnl,
                            "win_rate": result.win_rate,
                            "trades": result.total_trades,
                        }
                    )
                except Exception as exc:
                    rows.append(
                        {
                            "strategy": config.name,
                            "sharpe": 0.0,
                            "net_pnl": 0.0,
                            "win_rate": 0.0,
                            "trades": 0,
                            "error": str(exc),
                        }
                    )

            if not rows:
                continue

            metrics_df = (
                pd.DataFrame(rows)
                .sort_values("sharpe", ascending=False)
                .reset_index(drop=True)
            )
            metrics_df.index = metrics_df.index + 1  # 1-based rank

            self._regime_metrics[regime_id] = metrics_df
            self._regime_rankings[regime_id] = metrics_df["strategy"].tolist()

        self._is_fitted = True
        return self

    # ------------------------------------------------------------------ #
    #  select_strategies                                                   #
    # ------------------------------------------------------------------ #

    def select_strategies(
        self, current_regime: int, top_n: int = 3
    ) -> List[str]:
        """Return the top-N performing strategy names for the given regime.

        Args:
            current_regime: Regime integer (0=low, 1=normal, 2=high, 3=extreme).
            top_n: Number of top strategies to return. Default 3.

        Returns:
            List of strategy names sorted by descending in-regime Sharpe ratio.
            Falls back to all strategy names (in order) if the regime was not
            seen during fitting.
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before select_strategies().")

        ranking = self._regime_rankings.get(current_regime)
        if ranking is None:
            # Regime not seen during training – return all strategies
            return [config.name for _, config in self.strategies][:top_n]

        return ranking[:top_n]

    # ------------------------------------------------------------------ #
    #  regime_strategy_map                                                 #
    # ------------------------------------------------------------------ #

    def regime_strategy_map(self, top_n: int = 3) -> Dict[str, List[str]]:
        """Return the full regime -> [strategy] mapping using human labels.

        Args:
            top_n: Number of top strategies per regime. Default 3.

        Returns:
            Dict keyed by regime label string (e.g. 'low_vol') mapping to list of
            top strategy names.
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before regime_strategy_map().")

        result = {}
        for regime_id, ranking in self._regime_rankings.items():
            label = REGIME_LABELS.get(regime_id, f"regime_{regime_id}")
            result[label] = ranking[:top_n]

        return result

    # ------------------------------------------------------------------ #
    #  summary                                                             #
    # ------------------------------------------------------------------ #

    def summary(self) -> pd.DataFrame:
        """Return a summary DataFrame of all regime -> strategy metrics.

        Returns:
            DataFrame with columns: Regime, Rank, Strategy, Sharpe, Net PnL,
            Win Rate, Trades.
        """
        if not self._is_fitted:
            raise RuntimeError("Call fit() before summary().")

        rows = []
        for regime_id, metrics_df in sorted(self._regime_metrics.items()):
            label = REGIME_LABELS.get(regime_id, f"regime_{regime_id}")
            for rank, row in metrics_df.iterrows():
                rows.append(
                    {
                        "Regime": label,
                        "Rank": rank,
                        "Strategy": row["strategy"],
                        "Sharpe": round(row["sharpe"], 4),
                        "Net PnL": round(row["net_pnl"], 2),
                        "Win Rate": round(row["win_rate"], 4),
                        "Trades": int(row["trades"]),
                    }
                )

        return pd.DataFrame(rows)
