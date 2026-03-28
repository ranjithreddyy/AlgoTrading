"""Parallel batch runner for backtesting multiple strategies / parameter sweeps."""

import itertools
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Type

import pandas as pd

from src.strategies.base import BacktestResult, Strategy, StrategyConfig
from src.backtests.engine import BacktestEngine


def _run_single(args: tuple) -> dict:
    """Worker function for parallel execution. Must be top-level for pickling."""
    strategy_class_path, config_dict, data_json = args

    # Reconstruct objects inside worker
    import importlib
    module_path, class_name = strategy_class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    strategy_class = getattr(module, class_name)

    config = StrategyConfig(**config_dict)
    strategy = strategy_class(config)

    from io import StringIO
    df = pd.read_json(StringIO(data_json), orient="split")

    engine = BacktestEngine()
    result = engine.run(strategy, df)

    # Convert to serializable dict (drop equity_curve for inter-process transfer)
    return {
        "strategy_name": result.strategy_name,
        "params": result.params,
        "total_trades": result.total_trades,
        "winning_trades": result.winning_trades,
        "losing_trades": result.losing_trades,
        "gross_pnl": result.gross_pnl,
        "net_pnl": result.net_pnl,
        "max_drawdown": result.max_drawdown,
        "sharpe_ratio": result.sharpe_ratio,
        "profit_factor": result.profit_factor,
        "win_rate": result.win_rate,
        "avg_trade_pnl": result.avg_trade_pnl,
        "total_trades_count": result.total_trades,
        "trades_detail": result.trades,
    }


class BatchRunner:
    """Run multiple strategies or parameter sweeps in parallel."""

    def __init__(self, n_workers: Optional[int] = None):
        self.n_workers = n_workers

    def run_all(
        self,
        strategies: List[tuple],  # list of (strategy_class, StrategyConfig)
        data_df: pd.DataFrame,
    ) -> List[BacktestResult]:
        """Run a list of (strategy_class, config) pairs in parallel."""
        data_json = data_df.to_json(orient="split", date_format="iso")

        tasks = []
        for strategy_class, config in strategies:
            class_path = f"{strategy_class.__module__}.{strategy_class.__name__}"
            config_dict = {
                "name": config.name,
                "family": config.family,
                "asset_class": config.asset_class,
                "params": config.params,
                "param_grid": config.param_grid,
            }
            tasks.append((class_path, config_dict, data_json))

        results = []
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            futures = {executor.submit(_run_single, task): task for task in tasks}
            for future in as_completed(futures):
                try:
                    rd = future.result()
                    result = BacktestResult(
                        strategy_name=rd["strategy_name"],
                        params=rd["params"],
                        total_trades=rd["total_trades"],
                        winning_trades=rd["winning_trades"],
                        losing_trades=rd["losing_trades"],
                        gross_pnl=rd["gross_pnl"],
                        net_pnl=rd["net_pnl"],
                        max_drawdown=rd["max_drawdown"],
                        sharpe_ratio=rd["sharpe_ratio"],
                        profit_factor=rd["profit_factor"],
                        win_rate=rd["win_rate"],
                        avg_trade_pnl=rd["avg_trade_pnl"],
                        equity_curve=[],
                        trades=rd["trades_detail"],
                    )
                    results.append(result)
                except Exception as e:
                    task_info = futures[future]
                    print(f"Error running {task_info[0]}: {e}")

        return results

    def run_parameter_sweep(
        self,
        strategy_class: Type[Strategy],
        param_grid: Dict[str, list],
        data_df: pd.DataFrame,
        base_config: Optional[StrategyConfig] = None,
    ) -> List[BacktestResult]:
        """Expand param grid into all combinations and run each."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())
        combos = list(itertools.product(*values))

        tasks = []
        for combo in combos:
            params = dict(zip(keys, combo))
            config = StrategyConfig(
                name=base_config.name if base_config else strategy_class.__strategy_name__,
                family=base_config.family if base_config else getattr(strategy_class, "__default_family__", "unknown"),
                asset_class=base_config.asset_class if base_config else "stock",
                params=params,
            )
            tasks.append((strategy_class, config))

        return self.run_all(tasks, data_df)

    @staticmethod
    def generate_leaderboard(results: List[BacktestResult]) -> pd.DataFrame:
        """Generate a leaderboard DataFrame sorted by Sharpe ratio."""
        rows = []
        for r in results:
            rows.append({
                "Strategy": r.strategy_name,
                "Params": str(r.params),
                "Trades": r.total_trades,
                "Win Rate": f"{r.win_rate:.1%}",
                "Net PnL": f"{r.net_pnl:.2f}",
                "Sharpe": f"{r.sharpe_ratio:.4f}",
                "Profit Factor": f"{r.profit_factor:.4f}",
                "Max DD": f"{r.max_drawdown:.2f}",
                "Avg Trade": f"{r.avg_trade_pnl:.2f}",
                "_sharpe_num": r.sharpe_ratio,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            df = df.sort_values("_sharpe_num", ascending=False).reset_index(drop=True)
            df.index = df.index + 1  # 1-based ranking
            df = df.drop(columns=["_sharpe_num"])
        return df

    @staticmethod
    def save_results(results: List[BacktestResult], output_dir: str):
        """Save results as JSON files."""
        os.makedirs(output_dir, exist_ok=True)
        for i, r in enumerate(results):
            fname = f"{r.strategy_name}_{i}.json"
            data = {
                "strategy_name": r.strategy_name,
                "params": r.params,
                "total_trades": r.total_trades,
                "winning_trades": r.winning_trades,
                "losing_trades": r.losing_trades,
                "gross_pnl": r.gross_pnl,
                "net_pnl": r.net_pnl,
                "max_drawdown": r.max_drawdown,
                "sharpe_ratio": r.sharpe_ratio,
                "profit_factor": r.profit_factor,
                "win_rate": r.win_rate,
                "avg_trade_pnl": r.avg_trade_pnl,
                "trades": r.trades,
            }
            with open(os.path.join(output_dir, fname), "w") as f:
                json.dump(data, f, indent=2, default=str)
        print(f"Saved {len(results)} results to {output_dir}/")
