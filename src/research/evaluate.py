"""Strategy evaluation utilities."""

import math
from typing import List

from src.strategies.base import BacktestResult


def evaluate_strategy(results: List[BacktestResult]) -> dict:
    """Evaluate a strategy across multiple backtest results (e.g. walk-forward folds).

    Returns a dict with aggregated performance metrics:
        - avg_sharpe, std_sharpe
        - avg_pnl, total_pnl
        - avg_win_rate
        - avg_profit_factor
        - max_drawdown_across_folds
        - consistency (fraction of folds with positive PnL)
        - is_viable (positive avg_pnl and consistency > 50%)
    """
    if not results:
        return {
            "avg_sharpe": 0.0,
            "std_sharpe": 0.0,
            "avg_pnl": 0.0,
            "total_pnl": 0.0,
            "avg_win_rate": 0.0,
            "avg_profit_factor": 0.0,
            "max_drawdown_across_folds": 0.0,
            "consistency": 0.0,
            "is_viable": False,
        }

    n = len(results)

    sharpes = [r.sharpe_ratio for r in results]
    pnls = [r.net_pnl for r in results]
    win_rates = [r.win_rate for r in results]
    profit_factors = [
        r.profit_factor for r in results if r.profit_factor != float("inf")
    ]
    drawdowns = [r.max_drawdown for r in results]

    avg_sharpe = sum(sharpes) / n
    mean_sq = sum((s - avg_sharpe) ** 2 for s in sharpes) / n
    std_sharpe = math.sqrt(mean_sq)

    avg_pnl = sum(pnls) / n
    total_pnl = sum(pnls)

    avg_win_rate = sum(win_rates) / n

    avg_profit_factor = (
        sum(profit_factors) / len(profit_factors) if profit_factors else 0.0
    )

    max_dd = max(drawdowns) if drawdowns else 0.0

    positive_folds = sum(1 for p in pnls if p > 0)
    consistency = positive_folds / n if n > 0 else 0.0

    is_viable = avg_pnl > 0 and consistency > 0.5

    return {
        "avg_sharpe": round(avg_sharpe, 4),
        "std_sharpe": round(std_sharpe, 4),
        "avg_pnl": round(avg_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "avg_win_rate": round(avg_win_rate, 4),
        "avg_profit_factor": round(avg_profit_factor, 4),
        "max_drawdown_across_folds": round(max_dd, 2),
        "consistency": round(consistency, 4),
        "is_viable": is_viable,
    }
