#!/usr/bin/env python3
"""Full portfolio backtest: all 10 stocks x all 9 strategies.

Steps:
  1. Load 10 NSE stocks (daily OHLCV).
  2. Run 9 strategies on each stock.
  3. Aggregate results into a strategy-level returns DataFrame.
  4. Compute strategy correlation matrix.
  5. Find top 3 uncorrelated strategy pairs.
  6. Run portfolio optimisation (equal weight, max Sharpe, risk parity).
  7. Compare portfolio approaches vs individual strategy results.
  8. Save correlation heatmap -> artifacts/reports/strategy_correlation.png
  9. Save portfolio results -> artifacts/reports/portfolio_backtest.html
"""

import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
import pandas as pd

from src.data.storage import DataStorage
from src.strategies.base import StrategyConfig
from src.strategies.registry import StrategyRegistry
from src.backtests.engine import BacktestEngine
from src.research.correlation import (
    compute_strategy_returns,
    correlation_matrix,
    plot_correlation_heatmap,
    find_uncorrelated_pairs,
    diversification_score,
)
from src.research.portfolio import PortfolioOptimizer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "SBIN", "HINDUNILVR", "BHARTIARTL", "KOTAKBANK", "LT",
]

ARTIFACTS_DIR = os.path.join(PROJECT_ROOT, "artifacts", "reports")
HEATMAP_PATH = os.path.join(ARTIFACTS_DIR, "strategy_correlation.png")
HTML_PATH = os.path.join(ARTIFACTS_DIR, "portfolio_backtest.html")

os.makedirs(ARTIFACTS_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_stock_data(symbol: str, storage: DataStorage) -> pd.DataFrame:
    """Load daily OHLCV from local storage."""
    df = storage.load_bars(symbol, "NSE", "day")
    if df.empty:
        print(f"  WARNING: no data for {symbol}")
    return df


def build_strategies(registry: StrategyRegistry) -> list:
    """Return list of (class, config) for all discovered strategies."""
    items = []
    for name in registry.list_all():
        cls = registry.get(name)
        instance = cls(StrategyConfig(name=name, family="", asset_class="stock"))
        params = instance.get_default_params()
        family = getattr(cls, "__default_family__", "unknown")
        config = StrategyConfig(
            name=name,
            family=family,
            asset_class="stock",
            params=params,
        )
        items.append((cls, config))
    return items


def run_strategy_on_stock(cls, config: StrategyConfig, df: pd.DataFrame):
    """Run a single strategy on a stock DataFrame. Returns BacktestResult or None."""
    if df.empty or len(df) < 20:
        return None
    try:
        engine = BacktestEngine()
        strategy = cls(config)
        return engine.run(strategy, df)
    except Exception as exc:
        return None


def aggregate_results_dict(all_results: dict) -> dict:
    """Merge multiple per-stock BacktestResult objects per strategy into one synthetic result.

    We concatenate all trades across stocks for each strategy.
    """
    from src.strategies.base import BacktestResult

    merged = {}
    for strategy_name, stock_results in all_results.items():
        all_trades = []
        for result in stock_results:
            if result is not None:
                all_trades.extend(result.trades)

        # Build a synthetic BacktestResult-like object with just .trades
        class _R:
            pass

        r = _R()
        r.trades = all_trades
        merged[strategy_name] = r

    return merged


def compute_individual_metrics(all_results: dict) -> pd.DataFrame:
    """Summarise per-strategy performance across all stocks."""
    rows = []
    for strategy_name, stock_results in all_results.items():
        valid = [r for r in stock_results if r is not None]
        if not valid:
            continue
        total_trades = sum(r.total_trades for r in valid)
        net_pnl = sum(r.net_pnl for r in valid)
        sharpes = [r.sharpe_ratio for r in valid]
        avg_sharpe = float(np.mean(sharpes)) if sharpes else 0.0
        win_rates = [r.win_rate for r in valid]
        avg_wr = float(np.mean(win_rates)) if win_rates else 0.0
        max_dds = [r.max_drawdown for r in valid]
        max_dd = float(np.max(max_dds)) if max_dds else 0.0

        rows.append({
            "Strategy": strategy_name,
            "Stocks": len(valid),
            "Total Trades": total_trades,
            "Net PnL": round(net_pnl, 2),
            "Avg Sharpe": round(avg_sharpe, 4),
            "Avg Win Rate": round(avg_wr, 4),
            "Max DD": round(max_dd, 2),
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Avg Sharpe", ascending=False).reset_index(drop=True)
        df.index = df.index + 1
    return df


# ---------------------------------------------------------------------------
# HTML report builder
# ---------------------------------------------------------------------------

def build_html_report(
    individual_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    corr_matrix_df: pd.DataFrame,
    uncorrelated_pairs: list,
    div_score: float,
    heatmap_rel_path: str,
) -> str:
    """Assemble a self-contained HTML report."""

    def df_to_html(df: pd.DataFrame, table_id: str = "") -> str:
        style = (
            'border-collapse:collapse;width:100%;font-size:13px;'
        )
        attrs = f'id="{table_id}" style="{style}"' if table_id else f'style="{style}"'
        return df.to_html(border=1, classes="data-table", table_id=table_id)

    pairs_html = ""
    if uncorrelated_pairs:
        pairs_html = "<ul>" + "".join(
            f"<li><b>{a}</b> vs <b>{b}</b></li>" for a, b in uncorrelated_pairs[:10]
        ) + "</ul>"
    else:
        pairs_html = "<p>No uncorrelated pairs found below threshold 0.3.</p>"

    heatmap_html = f'<img src="{heatmap_rel_path}" alt="Correlation Heatmap" style="max-width:700px;">'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Portfolio Backtest Report</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 32px; background: #f8f9fa; color: #222; }}
  h1 {{ color: #1a237e; }}
  h2 {{ color: #283593; border-bottom: 2px solid #c5cae9; padding-bottom: 4px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-bottom: 24px; background: #fff; }}
  th {{ background: #3f51b5; color: #fff; padding: 7px 10px; text-align: left; }}
  td {{ padding: 6px 10px; border: 1px solid #ddd; }}
  tr:nth-child(even) {{ background: #f3f3f3; }}
  .card {{ background: #fff; border-radius: 6px; padding: 16px 24px; margin-bottom: 28px;
           box-shadow: 0 1px 4px rgba(0,0,0,0.1); }}
  .metric {{ display: inline-block; margin-right: 32px; }}
  .metric .val {{ font-size: 22px; font-weight: bold; color: #3f51b5; }}
  .metric .lbl {{ font-size: 12px; color: #666; }}
</style>
</head>
<body>
<h1>Portfolio Backtest Report</h1>
<p>Stocks: {', '.join(STOCKS)}</p>

<div class="card">
  <h2>Diversification Score</h2>
  <div class="metric">
    <div class="val">{div_score:.3f}</div>
    <div class="lbl">Diversification Score (1 = perfectly diversified)</div>
  </div>
</div>

<div class="card">
  <h2>Individual Strategy Performance (all stocks aggregated)</h2>
  {individual_df.to_html(border=0)}
</div>

<div class="card">
  <h2>Portfolio Allocation Comparison</h2>
  {comparison_df.to_html(border=0)}
</div>

<div class="card">
  <h2>Strategy Correlation Matrix</h2>
  {heatmap_html}
  <br>
  {corr_matrix_df.round(3).to_html(border=0)}
</div>

<div class="card">
  <h2>Top Uncorrelated Strategy Pairs (|corr| &le; 0.3)</h2>
  {pairs_html}
</div>

</body>
</html>"""
    return html


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    t0 = time.time()
    print("=" * 70)
    print("PORTFOLIO BACKTEST")
    print("=" * 70)

    # 1. Discover strategies
    registry = StrategyRegistry()
    registry.auto_discover()
    strategy_names = registry.list_all()
    print(f"\nDiscovered {len(strategy_names)} strategies: {', '.join(strategy_names)}")

    strategy_items = build_strategies(registry)

    # 2. Load all 10 stocks
    storage = DataStorage(os.path.join(PROJECT_ROOT, "data"))
    stock_data = {}
    print(f"\nLoading {len(STOCKS)} stocks...")
    for sym in STOCKS:
        df = load_stock_data(sym, storage)
        stock_data[sym] = df
        print(f"  {sym}: {len(df)} bars")

    # 3. Run all strategies on all stocks
    print(f"\nRunning {len(strategy_items)} strategies x {len(STOCKS)} stocks ...")
    # all_results[strategy_name] = [BacktestResult | None, ...]  (one per stock)
    all_results: dict = {config.name: [] for _, config in strategy_items}

    for sym, df in stock_data.items():
        for cls, config in strategy_items:
            result = run_strategy_on_stock(cls, config, df)
            all_results[config.name].append(result)
        print(f"  Finished {sym}")

    # 4. Aggregate per-strategy
    individual_df = compute_individual_metrics(all_results)
    print("\n--- Individual Strategy Performance ---")
    print(individual_df.to_string())

    # 5. Build strategy returns DataFrame
    merged_results = aggregate_results_dict(all_results)
    returns_df = compute_strategy_returns(merged_results)
    print(f"\nReturns DataFrame shape: {returns_df.shape}  (dates x strategies)")

    # 6. Correlation matrix
    corr_df = correlation_matrix(returns_df)
    if not corr_df.empty:
        print("\n--- Correlation Matrix ---")
        print(corr_df.round(3).to_string())
    else:
        print("\nNot enough trades to build correlation matrix.")

    # 7. Save heatmap
    plot_correlation_heatmap(corr_df, HEATMAP_PATH)

    # 8. Find uncorrelated pairs
    pairs = find_uncorrelated_pairs(corr_df, threshold=0.3)
    print(f"\nUncorrelated pairs (|corr| <= 0.3): {len(pairs)} found")
    top3_pairs = pairs[:3]
    for a, b in top3_pairs:
        print(f"  {a}  <-->  {b}  (corr={corr_df.loc[a, b]:.3f})")

    # Diversification score
    div_score = diversification_score(returns_df)
    print(f"\nDiversification Score: {div_score:.4f}")

    # 9. Portfolio optimisation
    optimizer = PortfolioOptimizer()
    print("\n--- Portfolio Allocation Comparison ---")
    comparison_df = optimizer.compare_allocation_methods(returns_df)
    print(comparison_df.to_string())

    # 10. Save HTML report
    heatmap_rel = os.path.relpath(HEATMAP_PATH, ARTIFACTS_DIR)
    html_content = build_html_report(
        individual_df=individual_df,
        comparison_df=comparison_df,
        corr_matrix_df=corr_df if not corr_df.empty else pd.DataFrame({"Note": ["Insufficient data"]}),
        uncorrelated_pairs=pairs,
        div_score=div_score,
        heatmap_rel_path=heatmap_rel,
    )
    with open(HTML_PATH, "w") as fh:
        fh.write(html_content)
    print(f"\nSaved HTML report -> {HTML_PATH}")

    elapsed = time.time() - t0
    print(f"\nTotal time: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
