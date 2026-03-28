#!/usr/bin/env python3
"""Batch paper trading simulation across all symbols and all strategies.

Usage:
    python scripts/paper_trading_batch.py

Produces:
    - Console leaderboard table
    - artifacts/paper/batch_YYYY-MM-DD.json
    - artifacts/reports/paper_batch.html
"""

import asyncio
import json
import logging
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import base64
import io

from src.config.settings import DATA_DIR, ARTIFACTS_DIR
from src.data.storage import DataStorage
from src.strategies.base import StrategyConfig
from src.strategies.registry import global_registry
from src.live.session_manager import SessionManager
from src.live.signal_service import SignalService
from src.live.trade_loop import TradingLoop

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("paper_batch")

SYMBOLS = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN"]
EXCHANGE = "NSE"
INTERVAL = "day"
BARS = 100
EQUITY_FAMILIES = {"momentum", "mean_reversion"}  # skip pure options strategies


def discover_strategies() -> List[str]:
    """Auto-discover all strategies; filter to equity-compatible ones."""
    global_registry.auto_discover()
    all_strats = global_registry.list_all()
    # Filter out option-specific strategies that won't work on equity OHLCV data
    # (they still work but may not trade — include all for completeness)
    return sorted(all_strats)


def build_strategy(name: str):
    """Build an instantiated strategy by name."""
    cls = global_registry.get(name)
    if cls is None:
        return None
    config = StrategyConfig(
        name=name,
        family=getattr(cls, "__default_family__", "unknown"),
        asset_class="stock",
        params=cls(StrategyConfig(name="tmp", family="", asset_class="")).get_default_params(),
    )
    return cls(config)


def compute_sharpe(trades: List[Dict]) -> float:
    """Compute annualised Sharpe from a list of trade net_pnl values."""
    if not trades:
        return 0.0
    pnls = [t["net_pnl"] for t in trades]
    n = len(pnls)
    if n < 2:
        return 0.0
    mean = sum(pnls) / n
    var = sum((x - mean) ** 2 for x in pnls) / n
    std = math.sqrt(var) if var > 0 else 1e-9
    return round((mean / std) * math.sqrt(252), 4)


async def run_single(symbol: str, strategy_name: str, bars: List[dict]) -> Dict[str, Any]:
    """Run one simulation and return a result dict."""
    strategy = build_strategy(strategy_name)
    if strategy is None:
        return {}

    session_mgr = SessionManager(config={"mode": "paper", "symbol": symbol})
    signal_svc = SignalService(strategies=[strategy])
    loop = TradingLoop(session_manager=session_mgr, signal_service=signal_svc)

    await loop.run_simulation(bars=bars, symbol=symbol, delay=0.0)

    trades = loop.trades
    total = len(trades)
    winners = [t for t in trades if t["net_pnl"] > 0]
    total_pnl = round(sum(t["net_pnl"] for t in trades), 2)
    win_rate = round(len(winners) / total * 100, 1) if total else 0.0
    sharpe = compute_sharpe(trades)

    # Build equity curve
    equity = [0.0]
    for t in trades:
        equity.append(equity[-1] + t["net_pnl"])

    return {
        "symbol": symbol,
        "strategy": strategy_name,
        "bars": len(bars),
        "trades": total,
        "winners": len(winners),
        "losers": total - len(winners),
        "win_pct": win_rate,
        "total_pnl": total_pnl,
        "sharpe": sharpe,
        "equity_curve": equity,
        "trade_list": trades,
    }


def load_bars(symbol: str) -> List[dict]:
    """Load the most recent BARS bars for a symbol."""
    storage = DataStorage(str(DATA_DIR))
    df = storage.load_bars(symbol, EXCHANGE, INTERVAL)
    if df.empty:
        logger.warning("No data for %s", symbol)
        return []
    df = df.tail(BARS).reset_index(drop=True)
    bars = []
    for _, row in df.iterrows():
        bars.append({
            "date": str(row["date"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["volume"]),
        })
    return bars


def print_leaderboard(results: List[Dict]):
    """Print a combined leaderboard table."""
    if not results:
        print("No results to display.")
        return

    # Sort by Sharpe descending, then PnL
    ranked = sorted(results, key=lambda r: (r["sharpe"], r["total_pnl"]), reverse=True)

    header = f"{'#':>3}  {'Symbol':<12} {'Strategy':<22} {'Trades':>6} {'Win%':>7} {'PnL':>12} {'Sharpe':>8}"
    sep = "-" * len(header)
    print("\n" + "=" * len(header))
    print("  PAPER TRADING BATCH LEADERBOARD")
    print("=" * len(header))
    print(header)
    print(sep)
    for i, r in enumerate(ranked, 1):
        pnl_str = f"{r['total_pnl']:+.2f}"
        print(
            f"{i:3d}  {r['symbol']:<12} {r['strategy']:<22} {r['trades']:6d} "
            f"{r['win_pct']:6.1f}% {pnl_str:>12} {r['sharpe']:8.4f}"
        )
    print(sep)


def _encode_fig(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def build_equity_chart(results: List[Dict]) -> str:
    """Equity curves chart (one curve per symbol+strategy combo)."""
    fig, ax = plt.subplots(figsize=(14, 6))
    for r in results:
        if r.get("equity_curve") and len(r["equity_curve"]) > 1:
            label = f"{r['symbol']}/{r['strategy']}"
            ax.plot(r["equity_curve"], label=label, linewidth=1.0, alpha=0.8)
    ax.set_title("Equity Curves — All Symbol/Strategy Combinations")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative PnL")
    ax.legend(fontsize=6, loc="best", ncol=3)
    ax.grid(True, alpha=0.3)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    return _encode_fig(fig)


def build_pnl_heatmap(results: List[Dict], strategies: List[str], symbols: List[str]) -> str:
    """PnL heatmap: rows = symbols, cols = strategies."""
    data = {}
    for r in results:
        data[(r["symbol"], r["strategy"])] = r["total_pnl"]

    import numpy as np
    matrix = []
    for sym in symbols:
        row = [data.get((sym, s), 0.0) for s in strategies]
        matrix.append(row)

    matrix_arr = [[v for v in row] for row in matrix]

    fig, ax = plt.subplots(figsize=(max(8, len(strategies) * 1.4), max(4, len(symbols) * 0.7)))
    max_abs = max(abs(v) for row in matrix_arr for v in row) or 1.0
    im = ax.imshow(matrix_arr, cmap="RdYlGn", aspect="auto", vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(range(len(strategies)))
    ax.set_xticklabels(strategies, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(symbols)))
    ax.set_yticklabels(symbols, fontsize=9)
    ax.set_title("PnL Heatmap (Symbol vs Strategy)")
    plt.colorbar(im, ax=ax, label="Net PnL")
    for i, sym in enumerate(symbols):
        for j, strat in enumerate(strategies):
            val = matrix_arr[i][j]
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", fontsize=7,
                    color="white" if abs(val) > max_abs * 0.6 else "black")
    fig.tight_layout()
    return _encode_fig(fig)


def generate_html_report(
    results: List[Dict],
    strategies: List[str],
    symbols: List[str],
    output_path: str,
) -> str:
    """Generate a comprehensive HTML batch report."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ranked = sorted(results, key=lambda r: (r["sharpe"], r["total_pnl"]), reverse=True)

    # Charts
    equity_img = build_equity_chart(ranked)
    heatmap_img = build_pnl_heatmap(results, strategies, symbols)

    # Leaderboard rows
    lb_rows = ""
    for i, r in enumerate(ranked, 1):
        viable_cls = "viable" if r["total_pnl"] > 0 else "not-viable"
        lb_rows += f"""
        <tr class="{viable_cls}">
            <td>{i}</td>
            <td>{r['symbol']}</td>
            <td>{r['strategy']}</td>
            <td>{r['trades']}</td>
            <td>{r['win_pct']:.1f}%</td>
            <td>{r['total_pnl']:+.2f}</td>
            <td>{r['sharpe']:.4f}</td>
        </tr>"""

    # Per-symbol breakdown
    sym_sections = ""
    for sym in symbols:
        sym_results = sorted(
            [r for r in results if r["symbol"] == sym],
            key=lambda r: r["sharpe"],
            reverse=True,
        )
        sym_rows = ""
        for r in sym_results:
            cls = "viable" if r["total_pnl"] > 0 else "not-viable"
            sym_rows += f"""
            <tr class="{cls}">
                <td>{r['strategy']}</td>
                <td>{r['trades']}</td>
                <td>{r['win_pct']:.1f}%</td>
                <td>{r['total_pnl']:+.2f}</td>
                <td>{r['sharpe']:.4f}</td>
            </tr>"""
        sym_sections += f"""
        <h3>{sym}</h3>
        <table>
            <thead><tr>
                <th>Strategy</th><th>Trades</th><th>Win%</th><th>PnL</th><th>Sharpe</th>
            </tr></thead>
            <tbody>{sym_rows}</tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paper Trading Batch Report</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 1300px; margin: 0 auto; padding: 20px;
        background: #f5f5f5; color: #333;
    }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2 {{ color: #16213e; margin-top: 30px; }}
    h3 {{ color: #444; margin-top: 20px; }}
    .timestamp {{ color: #666; font-size: 0.9em; }}
    table {{
        width: 100%; border-collapse: collapse; margin: 15px 0;
        background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th {{
        background: #16213e; color: white; padding: 10px 12px;
        text-align: left; font-size: 0.85em;
    }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.85em; }}
    tr:hover {{ background: #f0f4ff; }}
    tr.viable td {{ color: #155724; }}
    tr.not-viable td {{ color: #721c24; }}
    .chart {{ width: 100%; max-width: 1200px; margin: 15px 0; }}
    .summary-box {{
        background: white; border-radius: 8px; padding: 15px;
        margin: 10px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        display: inline-block; margin-right: 15px; min-width: 160px;
        text-align: center;
    }}
    .summary-box .val {{ font-size: 1.8em; font-weight: bold; color: #16213e; }}
    .summary-box .lbl {{ font-size: 0.8em; color: #666; }}
</style>
</head>
<body>
<h1>Paper Trading Batch Report</h1>
<p class="timestamp">Generated: {timestamp} | Symbols: {len(symbols)} | Strategies: {len(strategies)} | Bars: {BARS}</p>

<h2>Summary</h2>
<div>
    <div class="summary-box">
        <div class="val">{len(results)}</div>
        <div class="lbl">Combinations</div>
    </div>
    <div class="summary-box">
        <div class="val">{sum(r['trades'] for r in results)}</div>
        <div class="lbl">Total Trades</div>
    </div>
    <div class="summary-box">
        <div class="val">{sum(1 for r in results if r['total_pnl'] > 0)}</div>
        <div class="lbl">Profitable Combos</div>
    </div>
    <div class="summary-box">
        <div class="val">{max((r['sharpe'] for r in results), default=0):.4f}</div>
        <div class="lbl">Best Sharpe</div>
    </div>
</div>

<h2>Combined Leaderboard (ranked by Sharpe)</h2>
<table>
    <thead><tr>
        <th>#</th><th>Symbol</th><th>Strategy</th><th>Trades</th>
        <th>Win%</th><th>PnL</th><th>Sharpe</th>
    </tr></thead>
    <tbody>{lb_rows}</tbody>
</table>

<h2>Equity Curves</h2>
<img src="data:image/png;base64,{equity_img}" alt="Equity Curves" class="chart">

<h2>PnL Heatmap</h2>
<img src="data:image/png;base64,{heatmap_img}" alt="PnL Heatmap" class="chart">

<h2>Per-Symbol Breakdown</h2>
{sym_sections}

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return output_path


async def main():
    print("=" * 60)
    print("  PAPER TRADING BATCH RUNNER")
    print(f"  Symbols : {', '.join(SYMBOLS)}")
    print(f"  Bars    : {BARS} (most recent, daily interval)")
    print("=" * 60)

    strategies = discover_strategies()
    print(f"\n  Found {len(strategies)} strategies: {', '.join(strategies)}")

    # Load data for all symbols
    print("\n  Loading bar data...")
    symbol_bars: Dict[str, List[dict]] = {}
    for sym in SYMBOLS:
        bars = load_bars(sym)
        symbol_bars[sym] = bars
        print(f"    {sym}: {len(bars)} bars")

    # Run all combinations
    results: List[Dict] = []
    total_combos = len(SYMBOLS) * len(strategies)
    done = 0

    print(f"\n  Running {total_combos} simulations ({len(SYMBOLS)} symbols × {len(strategies)} strategies)...\n")

    for sym in SYMBOLS:
        bars = symbol_bars[sym]
        if not bars:
            print(f"  [SKIP] {sym}: no data")
            continue
        for strat_name in strategies:
            done += 1
            print(f"  [{done:3d}/{total_combos}] {sym} / {strat_name} ...", end=" ", flush=True)
            try:
                result = await run_single(sym, strat_name, bars)
                if result:
                    results.append(result)
                    pnl_str = f"{result['total_pnl']:+.2f}"
                    print(f"trades={result['trades']:3d}  pnl={pnl_str:>10}  sharpe={result['sharpe']:7.4f}")
                else:
                    print("SKIPPED")
            except Exception as e:
                print(f"ERROR: {e}")
                logger.exception("Error running %s / %s", sym, strat_name)

    print(f"\n  Completed {len(results)} simulations.")

    # Print leaderboard
    print_leaderboard(results)

    # Save JSON artifact
    paper_dir = ARTIFACTS_DIR / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_path = paper_dir / f"batch_{date_str}.json"

    # Serialize (remove non-serializable equity_curve from JSON, keep trade list)
    json_results = []
    for r in results:
        jr = {k: v for k, v in r.items() if k != "equity_curve"}
        json_results.append(jr)

    with open(json_path, "w") as f:
        json.dump({
            "date": date_str,
            "symbols": SYMBOLS,
            "strategies": strategies,
            "bars": BARS,
            "interval": INTERVAL,
            "results": json_results,
        }, f, indent=2, default=str)
    print(f"\n  JSON saved: {json_path}")

    # Generate HTML report
    reports_dir = ARTIFACTS_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / "paper_batch.html"
    generate_html_report(results, strategies, SYMBOLS, str(html_path))
    print(f"  HTML saved: {html_path}")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
