"""Walk-forward validation for strategy evaluation."""

from typing import List, Optional, Tuple, Type

import pandas as pd

from src.backtests.engine import BacktestEngine
from src.strategies.base import BacktestResult, Strategy, StrategyConfig


class WalkForwardValidator:
    """Rolling walk-forward validation.

    Divides data into rolling windows: train on N days, test on M days,
    slide forward. An embargo gap between train and test avoids lookahead bias.
    """

    def __init__(
        self,
        train_days: int,
        test_days: int,
        n_splits: Optional[int] = None,
        embargo_days: int = 1,
    ):
        self.train_days = train_days
        self.test_days = test_days
        self.n_splits = n_splits
        self.embargo_days = embargo_days

    def split(self, df: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """Yield (train_df, test_df) pairs from rolling windows.

        The DataFrame must have a 'date' column (or index).
        """
        work = df.copy()
        if "date" not in work.columns:
            work = work.reset_index()

        work["date"] = pd.to_datetime(work["date"], utc=True)
        work = work.sort_values("date").reset_index(drop=True)

        total_rows = len(work)
        window = self.train_days + self.embargo_days + self.test_days

        if total_rows < window:
            raise ValueError(
                f"Not enough data: need at least {window} rows, got {total_rows}"
            )

        splits = []
        start = 0

        while True:
            train_end = start + self.train_days
            test_start = train_end + self.embargo_days
            test_end = test_start + self.test_days

            if test_end > total_rows:
                break

            train_df = work.iloc[start:train_end].copy()
            test_df = work.iloc[test_start:test_end].copy()
            splits.append((train_df, test_df))

            # Slide forward by test_days
            start += self.test_days

            if self.n_splits is not None and len(splits) >= self.n_splits:
                break

        return splits

    def validate(
        self,
        strategy_class: Type[Strategy],
        strategy_config: StrategyConfig,
        df: pd.DataFrame,
    ) -> List[BacktestResult]:
        """Run walk-forward validation on a strategy.

        For each fold, the strategy is instantiated fresh and backtested
        on the test portion only (train portion is for warmup context).

        Returns a list of BacktestResult, one per fold.
        """
        splits = self.split(df)
        engine = BacktestEngine()
        results = []

        for train_df, test_df in splits:
            # Instantiate a fresh strategy per fold
            strategy = strategy_class(strategy_config)

            # Warm up the strategy on training data (no trades recorded)
            for _, row in train_df.iterrows():
                bar = {
                    "date": str(row["date"]),
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": float(row["volume"]),
                }
                strategy.on_bar(bar, {"position": None})

            # Run the actual backtest on test data
            result = engine.run(strategy, test_df)
            results.append(result)

        return results

    def summary(self, results: List[BacktestResult]) -> dict:
        """Aggregate out-of-sample metrics across folds."""
        if not results:
            return {
                "n_folds": 0,
                "avg_sharpe": 0.0,
                "avg_pnl": 0.0,
                "total_pnl": 0.0,
                "avg_win_rate": 0.0,
                "avg_profit_factor": 0.0,
                "max_drawdown": 0.0,
                "consistency": 0.0,
            }

        n = len(results)
        sharpes = [r.sharpe_ratio for r in results]
        pnls = [r.net_pnl for r in results]
        win_rates = [r.win_rate for r in results]
        profit_factors = [
            r.profit_factor for r in results if r.profit_factor != float("inf")
        ]
        drawdowns = [r.max_drawdown for r in results]
        positive_folds = sum(1 for p in pnls if p > 0)

        return {
            "n_folds": n,
            "avg_sharpe": round(sum(sharpes) / n, 4),
            "avg_pnl": round(sum(pnls) / n, 2),
            "total_pnl": round(sum(pnls), 2),
            "avg_win_rate": round(sum(win_rates) / n, 4),
            "avg_profit_factor": round(
                sum(profit_factors) / len(profit_factors), 4
            )
            if profit_factors
            else 0.0,
            "max_drawdown": round(max(drawdowns), 2) if drawdowns else 0.0,
            "consistency": round(positive_folds / n, 4) if n > 0 else 0.0,
        }
