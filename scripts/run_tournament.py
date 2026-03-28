#!/usr/bin/env python3
"""CLI script to run a walk-forward strategy tournament and generate an HTML report."""

import argparse
import glob
import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd

from src.research.selection import StrategyTournament
from src.research.walk_forward import WalkForwardValidator
from src.backtests.reports import generate_html_report
from src.strategies.base import StrategyConfig
from src.strategies.registry import StrategyRegistry, global_registry


def find_data_file(symbol: str, interval: str) -> str:
    """Locate the most recent data file for a symbol/interval."""
    base = os.path.join(
        os.path.dirname(__file__), "..", "data", "market", "NSE", symbol, interval
    )
    base = os.path.abspath(base)

    if not os.path.isdir(base):
        raise FileNotFoundError(f"Data directory not found: {base}")

    # Try dated files first, then generic data.csv
    csv_files = sorted(glob.glob(os.path.join(base, "*.csv")))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files in {base}")

    # Prefer the dated file (longer name) over generic data.csv
    dated = [f for f in csv_files if os.path.basename(f) != "data.csv"]
    return dated[-1] if dated else csv_files[-1]


def main():
    parser = argparse.ArgumentParser(description="Run strategy tournament")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g. RELIANCE)")
    parser.add_argument("--interval", default="day", help="Data interval (default: day)")
    parser.add_argument("--train-days", type=int, default=200, help="Training window size")
    parser.add_argument("--test-days", type=int, default=50, help="Test window size")
    parser.add_argument("--embargo-days", type=int, default=1, help="Embargo gap between train/test")
    parser.add_argument("--output-dir", default=None, help="Output directory for report")
    args = parser.parse_args()

    # Load data
    data_path = find_data_file(args.symbol, args.interval)
    print(f"Loading data from: {data_path}")
    df = pd.read_csv(data_path)
    print(f"Data shape: {df.shape}")

    # Discover strategies
    registry = StrategyRegistry()
    registry.auto_discover()
    strategy_names = registry.list_all()
    print(f"Discovered strategies: {strategy_names}")

    if not strategy_names:
        print("No strategies found!")
        sys.exit(1)

    # Build tournament
    tournament = StrategyTournament()
    for name in strategy_names:
        cls = registry.get(name)
        config = StrategyConfig(
            name=name,
            family=getattr(cls, "__default_family__", "unknown"),
            asset_class="stock",
        )
        tournament.add_strategy(name, cls, config)

    # Run tournament
    wf_params = {
        "train_days": args.train_days,
        "test_days": args.test_days,
        "embargo_days": args.embargo_days,
    }
    print(f"\nRunning walk-forward tournament (train={args.train_days}, test={args.test_days}, embargo={args.embargo_days})...")
    leaderboard = tournament.run_tournament(df, wf_params)

    print("\n=== LEADERBOARD ===")
    print(leaderboard.to_string())

    # Collect all per-fold results for HTML report
    all_results = []
    for name in strategy_names:
        fold_results = tournament.get_results(name)
        all_results.extend(fold_results)

    # Generate HTML report
    output_dir = args.output_dir or os.path.join(
        os.path.dirname(__file__), "..", "artifacts", "reports"
    )
    output_dir = os.path.abspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(
        output_dir, f"tournament_{args.symbol}_{args.interval}.html"
    )
    generate_html_report(
        all_results,
        report_path,
        title=f"Walk-Forward Tournament: {args.symbol} ({args.interval})",
    )
    print(f"\nHTML report saved to: {report_path}")


if __name__ == "__main__":
    main()
