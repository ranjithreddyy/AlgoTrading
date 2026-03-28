"""Strategy selection and tournament ranking."""

from typing import Dict, List, Optional, Type

import pandas as pd

from src.research.evaluate import evaluate_strategy
from src.research.walk_forward import WalkForwardValidator
from src.strategies.base import BacktestResult, Strategy, StrategyConfig


class StrategyTournament:
    """Run walk-forward validation on multiple strategies and rank them."""

    def __init__(self):
        self._entries: List[Dict] = []

    def add_strategy(
        self, name: str, strategy_class: Type[Strategy], config: StrategyConfig
    ):
        """Register a strategy for the tournament."""
        self._entries.append(
            {"name": name, "strategy_class": strategy_class, "config": config}
        )

    def run_tournament(
        self,
        df: pd.DataFrame,
        walk_forward_params: Optional[Dict] = None,
    ) -> pd.DataFrame:
        """Run walk-forward validation on all registered strategies.

        Args:
            df: Market data DataFrame.
            walk_forward_params: Dict with keys train_days, test_days,
                                 n_splits (optional), embargo_days (optional).
                                 Defaults to train_days=200, test_days=50.

        Returns:
            DataFrame leaderboard ranked by OOS Sharpe (descending).
        """
        if walk_forward_params is None:
            walk_forward_params = {}

        wf = WalkForwardValidator(
            train_days=walk_forward_params.get("train_days", 200),
            test_days=walk_forward_params.get("test_days", 50),
            n_splits=walk_forward_params.get("n_splits"),
            embargo_days=walk_forward_params.get("embargo_days", 1),
        )

        rows = []
        self._all_results: Dict[str, List[BacktestResult]] = {}

        for entry in self._entries:
            name = entry["name"]
            try:
                results = wf.validate(
                    entry["strategy_class"], entry["config"], df
                )
                metrics = evaluate_strategy(results)
                self._all_results[name] = results

                rows.append(
                    {
                        "Strategy": name,
                        "Folds": metrics.get("avg_sharpe", 0) and len(results),
                        "Avg Sharpe": metrics["avg_sharpe"],
                        "Std Sharpe": metrics["std_sharpe"],
                        "Avg PnL": metrics["avg_pnl"],
                        "Total PnL": metrics["total_pnl"],
                        "Avg Win Rate": metrics["avg_win_rate"],
                        "Avg PF": metrics["avg_profit_factor"],
                        "Max DD": metrics["max_drawdown_across_folds"],
                        "Consistency": metrics["consistency"],
                        "Viable": metrics["is_viable"],
                    }
                )
            except Exception as e:
                print(f"Error running {name}: {e}")
                rows.append(
                    {
                        "Strategy": name,
                        "Folds": 0,
                        "Avg Sharpe": 0.0,
                        "Std Sharpe": 0.0,
                        "Avg PnL": 0.0,
                        "Total PnL": 0.0,
                        "Avg Win Rate": 0.0,
                        "Avg PF": 0.0,
                        "Max DD": 0.0,
                        "Consistency": 0.0,
                        "Viable": False,
                    }
                )

        leaderboard = pd.DataFrame(rows)
        if not leaderboard.empty:
            leaderboard = leaderboard.sort_values(
                "Avg Sharpe", ascending=False
            ).reset_index(drop=True)
            leaderboard.index = leaderboard.index + 1  # 1-based ranking

        return leaderboard

    def get_results(self, name: str) -> List[BacktestResult]:
        """Get per-fold results for a strategy after tournament completes."""
        return self._all_results.get(name, [])

    def get_all_results(self) -> Dict[str, List[BacktestResult]]:
        """Get all per-fold results keyed by strategy name."""
        return getattr(self, "_all_results", {})
