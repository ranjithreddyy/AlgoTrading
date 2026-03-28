#!/usr/bin/env python3
"""CLI entry point for running backtests on all or specific strategies."""

import argparse
import glob
import os
import sys
import time

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

from src.strategies.base import StrategyConfig
from src.strategies.registry import StrategyRegistry, global_registry
from src.backtests.engine import BacktestEngine
from src.backtests.batch_runner import BatchRunner


def load_data(symbol: str, interval: str, exchange: str = "NSE") -> pd.DataFrame:
    """Load CSV data from data/market/{exchange}/{symbol}/{interval}/."""
    data_dir = os.path.join(PROJECT_ROOT, "data", "market", exchange, symbol, interval)
    if not os.path.isdir(data_dir):
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    csv_files = sorted(glob.glob(os.path.join(data_dir, "*.csv")))
    if not csv_files:
        print(f"Error: no CSV files found in {data_dir}")
        sys.exit(1)

    frames = []
    for f in csv_files:
        df = pd.read_csv(f, parse_dates=["date"])
        frames.append(df)

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values("date").reset_index(drop=True)
    data = data.drop_duplicates(subset=["date"])

    print(f"Loaded {len(data)} bars for {symbol} ({interval}) from {len(csv_files)} file(s)")
    return data


def main():
    parser = argparse.ArgumentParser(description="Run strategy backtests")
    parser.add_argument("--all", action="store_true", help="Run all registered strategies")
    parser.add_argument("--strategy", type=str, default=None, help="Run a specific strategy by name")
    parser.add_argument("--symbol", type=str, default="RELIANCE", help="Symbol (default: RELIANCE)")
    parser.add_argument("--interval", type=str, default="day", help="Interval (default: day)")
    parser.add_argument("--sweep", action="store_true", help="Run parameter sweep for each strategy")
    parser.add_argument("--workers", type=int, default=None, help="Number of parallel workers")
    parser.add_argument("--output", type=str, default=None, help="Output directory for results")
    parser.add_argument("--exchange", type=str, default="NSE", help="Exchange (default: NSE). Use INDEX for index symbols.")
    args = parser.parse_args()

    # Auto-discover strategies
    global_registry.auto_discover()
    all_strategies = global_registry.list_all()
    print(f"Discovered {len(all_strategies)} strategies: {', '.join(all_strategies)}")

    if not args.all and args.strategy is None:
        parser.print_help()
        print("\nAvailable strategies:", ", ".join(all_strategies))
        sys.exit(0)

    # Load data
    data = load_data(args.symbol, args.interval, args.exchange)

    # Determine which strategies to run
    if args.all:
        strategy_names = all_strategies
    else:
        if args.strategy not in all_strategies:
            print(f"Error: strategy '{args.strategy}' not found. Available: {', '.join(all_strategies)}")
            sys.exit(1)
        strategy_names = [args.strategy]

    runner = BatchRunner(n_workers=args.workers)
    engine = BacktestEngine()
    all_results = []

    print(f"\nRunning {len(strategy_names)} strategy(ies)...")
    print("=" * 80)

    start = time.time()

    if args.sweep:
        # Parameter sweep mode
        for name in strategy_names:
            cls = global_registry.get(name)
            instance = cls(StrategyConfig(name=name, family="", asset_class="stock"))
            grid = instance.get_param_grid()
            n_combos = 1
            for v in grid.values():
                n_combos *= len(v)
            print(f"\nSweeping {name}: {n_combos} parameter combinations")
            results = runner.run_parameter_sweep(cls, grid, data)
            all_results.extend(results)
    else:
        # Default params mode - run in parallel
        tasks = []
        for name in strategy_names:
            cls = global_registry.get(name)
            instance = cls(StrategyConfig(name=name, family="", asset_class="stock"))
            defaults = instance.get_default_params()
            family = getattr(cls, "__default_family__", "unknown")
            config = StrategyConfig(
                name=name,
                family=family,
                asset_class="stock",
                params=defaults,
            )
            tasks.append((cls, config))

        all_results = runner.run_all(tasks, data)

    elapsed = time.time() - start

    # Generate and print leaderboard
    print(f"\nCompleted in {elapsed:.2f}s")
    print("=" * 80)
    print("\nLEADERBOARD")
    print("-" * 80)

    leaderboard = BatchRunner.generate_leaderboard(all_results)
    if leaderboard.empty:
        print("No results to display.")
    else:
        print(leaderboard.to_string())

    # Save if requested
    if args.output:
        BatchRunner.save_results(all_results, args.output)

    print()


if __name__ == "__main__":
    main()
