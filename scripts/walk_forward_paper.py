#!/usr/bin/env python3
"""Walk-Forward Paper Trading for RELIANCE.

Methodology:
  - Load 2yr daily data for RELIANCE
  - Walk-forward windows: every 60 days, train/evaluate on previous 200 days,
    then paper-trade the next 60 days
  - Track equity curve across all periods
  - Print a stability leaderboard showing which strategy won most folds

Usage:
    python scripts/walk_forward_paper.py
"""

import asyncio
import json
import logging
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
logger = logging.getLogger("walk_forward")

SYMBOL = "RELIANCE"
EXCHANGE = "NSE"
INTERVAL = "day"
TRAIN_WINDOW = 200   # bars used for training/evaluation
TEST_WINDOW = 60     # bars to paper-trade (out-of-sample)
STEP = 60            # step forward each fold


def discover_strategies() -> List[str]:
    global_registry.auto_discover()
    return sorted(global_registry.list_all())


def build_strategy(name: str):
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


def bars_from_df(df) -> List[dict]:
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


def compute_sharpe(pnls: List[float]) -> float:
    n = len(pnls)
    if n < 2:
        return 0.0
    mean = sum(pnls) / n
    var = sum((x - mean) ** 2 for x in pnls) / n
    std = math.sqrt(var) if var > 0 else 1e-9
    return round((mean / std) * math.sqrt(252), 4)


async def run_bars(bars: List[dict], strategy_name: str) -> Dict[str, Any]:
    """Run one simulation for given bars and return summary dict."""
    strategy = build_strategy(strategy_name)
    if strategy is None:
        return {"strategy": strategy_name, "trades": 0, "pnl": 0.0, "sharpe": 0.0, "trade_list": []}

    session_mgr = SessionManager(config={"mode": "paper", "symbol": SYMBOL})
    signal_svc = SignalService(strategies=[strategy])
    loop = TradingLoop(session_manager=session_mgr, signal_service=signal_svc)
    await loop.run_simulation(bars=bars, symbol=SYMBOL, delay=0.0)

    trades = loop.trades
    pnl = round(sum(t["net_pnl"] for t in trades), 2)
    pnls = [t["net_pnl"] for t in trades]
    sharpe = compute_sharpe(pnls)

    return {
        "strategy": strategy_name,
        "trades": len(trades),
        "pnl": pnl,
        "sharpe": sharpe,
        "trade_list": trades,
    }


def _encode_fig(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def build_equity_chart(equity_by_strategy: Dict[str, List[float]], fold_labels: List[str]) -> str:
    """Draw cumulative equity curve per strategy across all walk-forward folds."""
    fig, ax = plt.subplots(figsize=(14, 6))
    for strat_name, equity in equity_by_strategy.items():
        ax.plot(equity, label=strat_name, linewidth=1.2, alpha=0.85)
    ax.set_title(f"Walk-Forward Equity Curves — {SYMBOL} (all strategies)")
    ax.set_xlabel("Trade #")
    ax.set_ylabel("Cumulative PnL")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    return _encode_fig(fig)


def build_fold_bar_chart(fold_results: List[Dict], strategies: List[str]) -> str:
    """Bar chart showing PnL per fold per strategy."""
    n_folds = len(fold_results)
    n_strats = len(strategies)
    width = 0.8 / max(n_strats, 1)
    x_idx = list(range(n_folds))

    fig, ax = plt.subplots(figsize=(max(10, n_folds * 1.5), 6))
    for i, strat in enumerate(strategies):
        pnls = [fold["test_results"].get(strat, {}).get("pnl", 0.0) for fold in fold_results]
        offsets = [x + i * width for x in x_idx]
        colors = ["#2ecc71" if p >= 0 else "#e74c3c" for p in pnls]
        ax.bar(offsets, pnls, width=width, label=strat, color=colors, alpha=0.75)

    ax.set_xticks([x + width * (n_strats - 1) / 2 for x in x_idx])
    fold_labels = [f"Fold {i+1}" for i in range(n_folds)]
    ax.set_xticklabels(fold_labels, rotation=30, ha="right", fontsize=8)
    ax.set_title("PnL per Fold per Strategy")
    ax.set_ylabel("Net PnL")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.legend(fontsize=8, loc="best", ncol=3)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _encode_fig(fig)


def generate_html_report(
    fold_results: List[Dict],
    stability_board: List[Dict],
    equity_by_strategy: Dict[str, List[float]],
    strategies: List[str],
    output_path: str,
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    n_folds = len(fold_results)

    equity_img = build_equity_chart(equity_by_strategy, [f"F{i+1}" for i in range(n_folds)])
    fold_img = build_fold_bar_chart(fold_results, strategies)

    # Stability leaderboard
    sb_rows = ""
    for i, row in enumerate(stability_board, 1):
        cls = "viable" if row["total_pnl"] > 0 else "not-viable"
        sb_rows += f"""
        <tr class="{cls}">
            <td>{i}</td>
            <td>{row['strategy']}</td>
            <td>{row['folds_won']}/{n_folds}</td>
            <td>{row['folds_profitable']}/{n_folds}</td>
            <td>{row['total_pnl']:+.2f}</td>
            <td>{row['avg_sharpe']:.4f}</td>
            <td>{row['total_trades']}</td>
        </tr>"""

    # Fold details
    fold_section = ""
    for i, fold in enumerate(fold_results, 1):
        fold_rows = ""
        for strat in strategies:
            res = fold["test_results"].get(strat, {})
            pnl = res.get("pnl", 0.0)
            cls = "viable" if pnl > 0 else "not-viable"
            winner = " ★" if fold.get("winner") == strat else ""
            fold_rows += f"""
            <tr class="{cls}">
                <td>{strat}{winner}</td>
                <td>{res.get('trades', 0)}</td>
                <td>{pnl:+.2f}</td>
                <td>{res.get('sharpe', 0.0):.4f}</td>
            </tr>"""

        fold_section += f"""
        <h4>Fold {i}: train [{fold['train_start']} → {fold['train_end']}]
            | test [{fold['test_start']} → {fold['test_end']}]</h4>
        <table>
            <thead><tr>
                <th>Strategy</th><th>Trades</th><th>Test PnL</th><th>Sharpe</th>
            </tr></thead>
            <tbody>{fold_rows}</tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Walk-Forward Paper Trading — {SYMBOL}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 1300px; margin: 0 auto; padding: 20px;
        background: #f5f5f5; color: #333;
    }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2, h3, h4 {{ color: #16213e; margin-top: 20px; }}
    .timestamp {{ color: #666; font-size: 0.9em; }}
    table {{
        width: 100%; border-collapse: collapse; margin: 12px 0;
        background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th {{ background: #16213e; color: white; padding: 10px 12px; text-align: left; font-size: 0.85em; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.85em; }}
    tr:hover {{ background: #f0f4ff; }}
    tr.viable td {{ color: #155724; }}
    tr.not-viable td {{ color: #721c24; }}
    .chart {{ width: 100%; max-width: 1200px; margin: 15px 0; }}
</style>
</head>
<body>
<h1>Walk-Forward Paper Trading — {SYMBOL}</h1>
<p class="timestamp">Generated: {timestamp}</p>
<p>
    Train window: {TRAIN_WINDOW} bars | Test window: {TEST_WINDOW} bars |
    Step: {STEP} bars | Folds: {n_folds}
</p>

<h2>Stability Leaderboard</h2>
<p>Ranked by folds won (most out-of-sample periods with best PnL)</p>
<table>
    <thead><tr>
        <th>#</th><th>Strategy</th><th>Folds Won</th>
        <th>Profitable Folds</th><th>Total PnL</th>
        <th>Avg Sharpe</th><th>Total Trades</th>
    </tr></thead>
    <tbody>{sb_rows}</tbody>
</table>

<h2>Equity Curves (across all folds)</h2>
<img src="data:image/png;base64,{equity_img}" alt="Equity" class="chart">

<h2>PnL per Fold</h2>
<img src="data:image/png;base64,{fold_img}" alt="Fold PnL" class="chart">

<h2>Fold Details</h2>
{fold_section}

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return output_path


async def main():
    print("=" * 65)
    print("  WALK-FORWARD PAPER TRADING")
    print(f"  Symbol : {SYMBOL} | Interval: {INTERVAL}")
    print(f"  Train  : {TRAIN_WINDOW} bars  |  Test: {TEST_WINDOW} bars  |  Step: {STEP}")
    print("=" * 65)

    strategies = discover_strategies()
    print(f"\n  Strategies ({len(strategies)}): {', '.join(strategies)}")

    # Load full dataset
    storage = DataStorage(str(DATA_DIR))
    df = storage.load_bars(SYMBOL, EXCHANGE, INTERVAL)
    if df.empty:
        print(f"  ERROR: No data for {SYMBOL}. Run data ingestion first.")
        sys.exit(1)

    df = df.reset_index(drop=True)
    total_bars = len(df)
    print(f"\n  Loaded {total_bars} bars: {df['date'].iloc[0]} → {df['date'].iloc[-1]}")

    # Build walk-forward folds
    folds: List[Tuple[int, int, int, int]] = []  # (train_start, train_end, test_start, test_end)
    train_end = TRAIN_WINDOW
    while train_end + TEST_WINDOW <= total_bars:
        train_start = max(0, train_end - TRAIN_WINDOW)
        test_start = train_end
        test_end = test_start + TEST_WINDOW
        folds.append((train_start, train_end, test_start, test_end))
        train_end += STEP

    if not folds:
        print(f"  Not enough data for walk-forward ({total_bars} bars < {TRAIN_WINDOW + TEST_WINDOW})")
        sys.exit(1)

    print(f"\n  Generated {len(folds)} walk-forward folds\n")

    # Track results across folds
    fold_results: List[Dict] = []
    # equity_by_strategy[strat] = cumulative PnL list (appended per fold)
    equity_by_strategy: Dict[str, List[float]] = {s: [0.0] for s in strategies}
    # fold_wins[strat] = number of folds where this strategy had the best test PnL
    fold_wins: Dict[str, int] = {s: 0 for s in strategies}
    fold_profitable: Dict[str, int] = {s: 0 for s in strategies}
    total_pnl_by_strat: Dict[str, float] = {s: 0.0 for s in strategies}
    total_trades_by_strat: Dict[str, int] = {s: 0 for s in strategies}
    all_sharpes: Dict[str, List[float]] = {s: [] for s in strategies}

    for fold_idx, (ts, te, ss, se) in enumerate(folds):
        train_df = df.iloc[ts:te].reset_index(drop=True)
        test_df = df.iloc[ss:se].reset_index(drop=True)
        test_bars = bars_from_df(test_df)
        train_bars = bars_from_df(train_df)  # noqa: F841 — available for future use

        t0 = str(train_df["date"].iloc[0])[:10]
        t1 = str(train_df["date"].iloc[-1])[:10]
        s0 = str(test_df["date"].iloc[0])[:10]
        s1 = str(test_df["date"].iloc[-1])[:10]

        print(f"  Fold {fold_idx+1}/{len(folds)}: train [{t0} → {t1}]  test [{s0} → {s1}]")

        test_results: Dict[str, Dict] = {}
        best_pnl = float("-inf")
        winner = None

        for strat_name in strategies:
            res = await run_bars(test_bars, strat_name)
            test_results[strat_name] = res

            # Update running totals
            total_pnl_by_strat[strat_name] += res["pnl"]
            total_trades_by_strat[strat_name] += res["trades"]
            if res["sharpe"] != 0.0:
                all_sharpes[strat_name].append(res["sharpe"])

            # Track per-strategy equity
            for t in res["trade_list"]:
                last = equity_by_strategy[strat_name][-1]
                equity_by_strategy[strat_name].append(last + t["net_pnl"])

            if res["pnl"] > best_pnl:
                best_pnl = res["pnl"]
                winner = strat_name

            if res["pnl"] > 0:
                fold_profitable[strat_name] += 1

            pnl_str = f"{res['pnl']:+.2f}"
            print(f"      {strat_name:<22}  trades={res['trades']:3d}  pnl={pnl_str:>10}  sharpe={res['sharpe']:7.4f}")

        if winner:
            fold_wins[winner] += 1
        print(f"      Winner: {winner}  (PnL: {best_pnl:+.2f})\n")

        fold_results.append({
            "fold": fold_idx + 1,
            "train_start": t0, "train_end": t1,
            "test_start": s0, "test_end": s1,
            "test_results": {s: r for s, r in test_results.items()},
            "winner": winner,
        })

    # Build stability leaderboard
    stability_board = []
    for strat in strategies:
        avg_sharpe = (
            sum(all_sharpes[strat]) / len(all_sharpes[strat])
            if all_sharpes[strat] else 0.0
        )
        stability_board.append({
            "strategy": strat,
            "folds_won": fold_wins[strat],
            "folds_profitable": fold_profitable[strat],
            "total_pnl": round(total_pnl_by_strat[strat], 2),
            "avg_sharpe": round(avg_sharpe, 4),
            "total_trades": total_trades_by_strat[strat],
        })

    # Sort by: folds_won (desc), folds_profitable (desc), total_pnl (desc)
    stability_board.sort(
        key=lambda r: (r["folds_won"], r["folds_profitable"], r["total_pnl"]),
        reverse=True,
    )

    # Print stability leaderboard
    print("\n" + "=" * 75)
    print("  STABILITY LEADERBOARD")
    print(f"  (Rankings across {len(folds)} walk-forward folds)")
    print("=" * 75)
    header = f"  {'#':>3}  {'Strategy':<22} {'Folds Won':>10} {'Profitable':>10} {'Total PnL':>12} {'Avg Sharpe':>11}"
    print(header)
    print("  " + "-" * 72)
    for i, row in enumerate(stability_board, 1):
        print(
            f"  {i:3d}  {row['strategy']:<22} "
            f"{row['folds_won']:>4}/{len(folds):<5} "
            f"{row['folds_profitable']:>4}/{len(folds):<5} "
            f"{row['total_pnl']:>+12.2f}  {row['avg_sharpe']:>10.4f}"
        )
    print("  " + "-" * 72)

    # Print overall winner
    top = stability_board[0]
    print(f"\n  Most Consistent Strategy: {top['strategy']}")
    print(f"    Folds Won      : {top['folds_won']}/{len(folds)}")
    print(f"    Profitable Folds: {top['folds_profitable']}/{len(folds)}")
    print(f"    Total PnL      : {top['total_pnl']:+.2f}")

    # Save JSON
    paper_dir = ARTIFACTS_DIR / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    json_path = paper_dir / f"walk_forward_{date_str}.json"

    # Serialize: remove trade_list from fold_results to keep file size manageable
    save_folds = []
    for fold in fold_results:
        sf = {k: v for k, v in fold.items() if k != "test_results"}
        sf["test_results"] = {}
        for strat, res in fold["test_results"].items():
            sf["test_results"][strat] = {k: v for k, v in res.items() if k != "trade_list"}
        save_folds.append(sf)

    with open(json_path, "w") as f:
        json.dump({
            "date": date_str,
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "train_window": TRAIN_WINDOW,
            "test_window": TEST_WINDOW,
            "step": STEP,
            "n_folds": len(folds),
            "strategies": strategies,
            "stability_leaderboard": stability_board,
            "folds": save_folds,
        }, f, indent=2, default=str)
    print(f"\n  JSON saved: {json_path}")

    # Generate HTML report
    reports_dir = ARTIFACTS_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / "walk_forward.html"
    generate_html_report(
        fold_results=fold_results,
        stability_board=stability_board,
        equity_by_strategy=equity_by_strategy,
        strategies=strategies,
        output_path=str(html_path),
    )
    print(f"  HTML saved: {html_path}")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
