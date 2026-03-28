#!/usr/bin/env python3
"""Daily Report Generator — aggregates all paper trade logs.

Usage:
    python scripts/generate_daily_report.py

Loads all JSON files from artifacts/paper/ and produces:
    - Console summary (today's trades, PnL, cumulative PnL, drawdown)
    - artifacts/reports/daily_YYYY-MM-DD.html
"""

import base64
import io
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.config.settings import ARTIFACTS_DIR

TODAY = datetime.now().strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all_paper_logs(paper_dir: Path) -> List[Dict]:
    """Load all JSON files from artifacts/paper/ directory."""
    if not paper_dir.exists():
        return []
    files = sorted(paper_dir.glob("*.json"))
    logs = []
    for f in files:
        try:
            with open(f) as fh:
                data = json.load(fh)
            data["_source_file"] = f.name
            data["_source_path"] = str(f)
            logs.append(data)
        except Exception as e:
            print(f"  Warning: could not load {f.name}: {e}")
    return logs


def extract_all_trades(logs: List[Dict]) -> List[Dict]:
    """Extract every trade from all log files, augmenting with metadata."""
    all_trades: List[Dict] = []

    for log in logs:
        # Handle batch log format: {results: [{symbol, strategy, trade_list: [...]}]}
        if "results" in log:
            for result in log.get("results", []):
                symbol = result.get("symbol", "UNKNOWN")
                strategy = result.get("strategy", "UNKNOWN")
                log_date = log.get("date", "UNKNOWN")
                for t in result.get("trade_list", []):
                    trade = {
                        **t,
                        "symbol": t.get("symbol") or symbol,
                        "strategy": strategy,
                        "log_date": log_date,
                        "source": log.get("_source_file", ""),
                    }
                    all_trades.append(trade)

        # Handle walk-forward log format: {folds: [{test_results: {strat: {trade_list}}}]}
        elif "folds" in log:
            log_date = log.get("date", "UNKNOWN")
            for fold in log.get("folds", []):
                for strat, res in fold.get("test_results", {}).items():
                    for t in res.get("trade_list", []):
                        trade = {
                            **t,
                            "symbol": t.get("symbol") or log.get("symbol", "UNKNOWN"),
                            "strategy": strat,
                            "log_date": log_date,
                            "fold": fold.get("fold", "?"),
                            "source": log.get("_source_file", ""),
                        }
                        all_trades.append(trade)

    return all_trades


def get_trade_date(trade: Dict) -> str:
    """Extract exit_date string (YYYY-MM-DD) from a trade."""
    raw = str(trade.get("exit_date", "") or trade.get("entry_date", "") or "")
    return raw[:10] if raw else "UNKNOWN"


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def compute_daily_pnl(trades: List[Dict]) -> Dict[str, float]:
    """Aggregate net PnL per exit date."""
    daily: Dict[str, float] = defaultdict(float)
    for t in trades:
        d = get_trade_date(t)
        daily[d] += t.get("net_pnl", 0.0)
    return dict(sorted(daily.items()))


def compute_cumulative_equity(daily_pnl: Dict[str, float]) -> Tuple[List[str], List[float]]:
    """Return (sorted dates, cumulative PnL list)."""
    dates = sorted(daily_pnl)
    cumulative = []
    running = 0.0
    for d in dates:
        running += daily_pnl[d]
        cumulative.append(round(running, 2))
    return dates, cumulative


def compute_max_drawdown(equity: List[float]) -> Tuple[float, int, int]:
    """Return (max_drawdown, peak_idx, trough_idx)."""
    if not equity:
        return 0.0, 0, 0
    peak = equity[0]
    peak_idx = 0
    max_dd = 0.0
    trough_idx = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
            peak_idx = i
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
            trough_idx = i
    return round(max_dd, 2), peak_idx, trough_idx


def compute_strategy_summary(trades: List[Dict]) -> List[Dict]:
    """Per-strategy summary across all logs."""
    strat_data: Dict[str, Dict] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
    for t in trades:
        strat = t.get("strategy", "UNKNOWN")
        strat_data[strat]["pnl"] += t.get("net_pnl", 0.0)
        strat_data[strat]["trades"] += 1
        if t.get("net_pnl", 0.0) > 0:
            strat_data[strat]["wins"] += 1

    result = []
    for strat, d in sorted(strat_data.items(), key=lambda x: x[1]["pnl"], reverse=True):
        wr = d["wins"] / d["trades"] * 100 if d["trades"] else 0.0
        result.append({
            "strategy": strat,
            "trades": d["trades"],
            "wins": d["wins"],
            "win_rate": round(wr, 1),
            "pnl": round(d["pnl"], 2),
        })
    return result


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def _encode_fig(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


def chart_daily_pnl(daily_pnl: Dict[str, float]) -> str:
    """Bar chart of daily PnL."""
    dates = sorted(daily_pnl)
    values = [daily_pnl[d] for d in dates]
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in values]

    fig, ax = plt.subplots(figsize=(max(10, len(dates) * 0.4), 5))
    ax.bar(range(len(dates)), values, color=colors, alpha=0.85, edgecolor="white")
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=45, ha="right", fontsize=7)
    ax.set_title("Daily PnL")
    ax.set_ylabel("Net PnL")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.6)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _encode_fig(fig)


def chart_cumulative_equity(dates: List[str], equity: List[float]) -> str:
    """Cumulative equity curve with drawdown shading."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(10, len(dates) * 0.4), 8),
                                    gridspec_kw={"height_ratios": [3, 1]}, sharex=True)

    # Equity curve
    ax1.plot(range(len(equity)), equity, color="#2980b9", linewidth=1.5, label="Cumulative PnL")
    ax1.fill_between(range(len(equity)), equity, 0,
                     where=[v >= 0 for v in equity], alpha=0.15, color="#2ecc71")
    ax1.fill_between(range(len(equity)), equity, 0,
                     where=[v < 0 for v in equity], alpha=0.15, color="#e74c3c")
    ax1.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax1.set_title("Cumulative PnL Equity Curve")
    ax1.set_ylabel("Cumulative PnL")
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=9)

    # Drawdown
    peak = equity[0] if equity else 0
    drawdowns = []
    for v in equity:
        if v > peak:
            peak = v
        drawdowns.append(v - peak)

    ax2.fill_between(range(len(drawdowns)), drawdowns, 0, alpha=0.4, color="#e74c3c")
    ax2.plot(drawdowns, color="#c0392b", linewidth=0.8)
    ax2.axhline(0, color="black", linewidth=0.8)
    ax2.set_title("Drawdown")
    ax2.set_ylabel("Drawdown")
    ax2.set_xticks(range(0, len(dates), max(1, len(dates) // 20)))
    ax2.set_xticklabels(
        [dates[i] for i in range(0, len(dates), max(1, len(dates) // 20))],
        rotation=45, ha="right", fontsize=7
    )
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    return _encode_fig(fig)


def chart_strategy_pnl(strategy_summary: List[Dict]) -> str:
    """Horizontal bar chart of total PnL per strategy."""
    if not strategy_summary:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        return _encode_fig(fig)

    names = [s["strategy"] for s in strategy_summary]
    pnls = [s["pnl"] for s in strategy_summary]
    colors = ["#2ecc71" if p >= 0 else "#e74c3c" for p in pnls]

    fig, ax = plt.subplots(figsize=(10, max(4, len(names) * 0.5)))
    bars = ax.barh(range(len(names)), pnls, color=colors, alpha=0.85, edgecolor="white")
    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.set_title("Cumulative PnL by Strategy")
    ax.set_xlabel("Net PnL")
    ax.grid(True, alpha=0.3, axis="x")
    # Add value labels
    for bar, pnl in zip(bars, pnls):
        ax.text(
            pnl + (max(abs(p) for p in pnls) * 0.01 if pnl >= 0 else -max(abs(p) for p in pnls) * 0.01),
            bar.get_y() + bar.get_height() / 2,
            f"{pnl:+.2f}", va="center", ha="left" if pnl >= 0 else "right", fontsize=8
        )
    fig.tight_layout()
    return _encode_fig(fig)


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_console_summary(
    all_trades: List[Dict],
    daily_pnl: Dict[str, float],
    equity: List[float],
    strategy_summary: List[Dict],
):
    today_trades = [t for t in all_trades if get_trade_date(t) == TODAY]
    today_pnl = sum(t.get("net_pnl", 0.0) for t in today_trades)
    cum_pnl = equity[-1] if equity else 0.0
    max_dd, _, _ = compute_max_drawdown(equity)

    print("\n" + "=" * 60)
    print("  DAILY REPORT SUMMARY")
    print(f"  Date              : {TODAY}")
    print("=" * 60)
    print(f"  Total log files   : multiple (see artifacts/paper/)")
    print(f"  Total trades loaded: {len(all_trades)}")
    print(f"  Total trading days : {len(daily_pnl)}")
    print()
    print(f"  Today ({TODAY}):")
    if today_trades:
        print(f"    Trades today    : {len(today_trades)}")
        print(f"    PnL today       : {today_pnl:+.2f}")
        for t in today_trades[:10]:
            print(f"      {t.get('symbol','?'):12s} {t.get('strategy','?'):22s}  {t.get('net_pnl',0):+.2f}")
    else:
        print("    No trades found for today.")
    print()
    print(f"  Cumulative PnL    : {cum_pnl:+.2f}")
    print(f"  Max Drawdown      : {max_dd:.2f}")

    # Expected vs actual (compare batch results if available)
    # We approximate "expected" as avg daily PnL from historical data
    if daily_pnl and len(daily_pnl) > 1:
        avg_daily = cum_pnl / len(daily_pnl)
        print(f"  Avg Daily PnL     : {avg_daily:+.2f}")
        if TODAY in daily_pnl:
            diff = today_pnl - avg_daily
            print(f"  vs. Expected (avg): {diff:+.2f} ({'above' if diff >= 0 else 'below'} average)")

    print()
    print("  Strategy Performance (all time):")
    for s in strategy_summary[:10]:
        print(f"    {s['strategy']:<22}  trades={s['trades']:4d}  win={s['win_rate']:5.1f}%  pnl={s['pnl']:+10.2f}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def generate_html_report(
    all_trades: List[Dict],
    daily_pnl: Dict[str, float],
    dates: List[str],
    equity: List[float],
    strategy_summary: List[Dict],
    output_path: str,
) -> str:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    today_trades = [t for t in all_trades if get_trade_date(t) == TODAY]
    today_pnl = round(sum(t.get("net_pnl", 0.0) for t in today_trades), 2)
    cum_pnl = round(equity[-1] if equity else 0.0, 2)
    max_dd, _, _ = compute_max_drawdown(equity)

    # Charts
    daily_pnl_img = chart_daily_pnl(daily_pnl) if daily_pnl else None
    equity_img = chart_cumulative_equity(dates, equity) if equity else None
    strategy_img = chart_strategy_pnl(strategy_summary) if strategy_summary else None

    # Expected vs actual
    avg_daily = cum_pnl / len(daily_pnl) if daily_pnl else 0.0
    today_vs_avg = today_pnl - avg_daily
    exp_vs_actual_str = (
        f"Today PnL ({today_pnl:+.2f}) vs avg ({avg_daily:+.2f}) = "
        f"<strong style='color:{'green' if today_vs_avg >= 0 else 'red'}'>{today_vs_avg:+.2f}</strong> "
        f"({'above' if today_vs_avg >= 0 else 'below'} average)"
        if daily_pnl else "No historical data available"
    )

    # Today's trades table
    today_rows = ""
    for t in sorted(today_trades, key=lambda x: x.get("exit_date", ""))[:50]:
        cls = "viable" if t.get("net_pnl", 0) > 0 else "not-viable"
        today_rows += f"""
        <tr class="{cls}">
            <td>{t.get('symbol','')}</td>
            <td>{t.get('strategy','')}</td>
            <td>{t.get('side','')}</td>
            <td>{str(t.get('entry_date',''))[:10]}</td>
            <td>{str(t.get('exit_date',''))[:10]}</td>
            <td>{t.get('entry_price',0):.2f}</td>
            <td>{t.get('exit_price',0):.2f}</td>
            <td>{t.get('net_pnl',0):+.2f}</td>
        </tr>"""

    if not today_rows:
        today_rows = "<tr><td colspan='8' style='text-align:center;color:#666'>No trades for today</td></tr>"

    # Strategy summary table
    strat_rows = ""
    for s in strategy_summary:
        cls = "viable" if s["pnl"] > 0 else "not-viable"
        strat_rows += f"""
        <tr class="{cls}">
            <td>{s['strategy']}</td>
            <td>{s['trades']}</td>
            <td>{s['wins']}</td>
            <td>{s['win_rate']:.1f}%</td>
            <td>{s['pnl']:+.2f}</td>
        </tr>"""

    # Daily PnL table (last 20 days)
    daily_rows = ""
    for d in sorted(daily_pnl)[-20:]:
        pnl = daily_pnl[d]
        cls = "viable" if pnl > 0 else "not-viable"
        is_today = " (Today)" if d == TODAY else ""
        daily_rows += f"""
        <tr class="{cls}">
            <td>{d}{is_today}</td>
            <td>{pnl:+.2f}</td>
        </tr>"""

    # Chart sections
    def img_section(title: str, b64: Optional[str], alt: str) -> str:
        if not b64:
            return ""
        return f"""
        <h2>{title}</h2>
        <img src="data:image/png;base64,{b64}" alt="{alt}" class="chart">"""

    pnl_color = "green" if today_pnl >= 0 else "#c0392b"
    cum_color = "green" if cum_pnl >= 0 else "#c0392b"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Daily Paper Trading Report — {TODAY}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 1300px; margin: 0 auto; padding: 20px;
        background: #f5f5f5; color: #333;
    }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2 {{ color: #16213e; margin-top: 30px; }}
    .timestamp {{ color: #666; font-size: 0.9em; }}
    .kpi-row {{ display: flex; gap: 15px; flex-wrap: wrap; margin: 15px 0; }}
    .kpi {{
        background: white; border-radius: 8px; padding: 15px 20px;
        min-width: 160px; text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .kpi .val {{ font-size: 2em; font-weight: bold; }}
    .kpi .lbl {{ font-size: 0.8em; color: #666; margin-top: 4px; }}
    table {{
        width: 100%; border-collapse: collapse; margin: 15px 0;
        background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th {{ background: #16213e; color: white; padding: 10px 12px; text-align: left; font-size: 0.85em; }}
    td {{ padding: 8px 12px; border-bottom: 1px solid #eee; font-size: 0.85em; }}
    tr:hover {{ background: #f0f4ff; }}
    tr.viable td {{ color: #155724; }}
    tr.not-viable td {{ color: #721c24; }}
    .chart {{ width: 100%; max-width: 1200px; margin: 15px 0; }}
    .exp-box {{
        background: white; border-radius: 8px; padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin: 10px 0;
        font-size: 0.95em;
    }}
</style>
</head>
<body>
<h1>Daily Paper Trading Report</h1>
<p class="timestamp">Generated: {timestamp} | Report date: {TODAY}</p>

<h2>Key Metrics</h2>
<div class="kpi-row">
    <div class="kpi">
        <div class="val" style="color:{pnl_color}">{today_pnl:+.2f}</div>
        <div class="lbl">Today's PnL</div>
    </div>
    <div class="kpi">
        <div class="val" style="color:{cum_color}">{cum_pnl:+.2f}</div>
        <div class="lbl">Cumulative PnL</div>
    </div>
    <div class="kpi">
        <div class="val" style="color:#c0392b">{max_dd:.2f}</div>
        <div class="lbl">Max Drawdown</div>
    </div>
    <div class="kpi">
        <div class="val">{len(today_trades)}</div>
        <div class="lbl">Trades Today</div>
    </div>
    <div class="kpi">
        <div class="val">{len(all_trades)}</div>
        <div class="lbl">Total Trades</div>
    </div>
    <div class="kpi">
        <div class="val">{len(daily_pnl)}</div>
        <div class="lbl">Trading Days</div>
    </div>
</div>

<h2>Expected vs Actual Performance</h2>
<div class="exp-box">{exp_vs_actual_str}</div>

<h2>Today's Trades ({TODAY})</h2>
<table>
    <thead><tr>
        <th>Symbol</th><th>Strategy</th><th>Side</th>
        <th>Entry Date</th><th>Exit Date</th>
        <th>Entry</th><th>Exit</th><th>Net PnL</th>
    </tr></thead>
    <tbody>{today_rows}</tbody>
</table>

{img_section("Daily PnL", daily_pnl_img, "Daily PnL")}

{img_section("Cumulative PnL &amp; Drawdown", equity_img, "Equity Curve")}

<h2>Recent Daily PnL (last 20 days)</h2>
<table>
    <thead><tr><th>Date</th><th>Net PnL</th></tr></thead>
    <tbody>{daily_rows}</tbody>
</table>

{img_section("Strategy Performance", strategy_img, "Strategy PnL")}

<h2>Strategy Summary (all-time)</h2>
<table>
    <thead><tr>
        <th>Strategy</th><th>Trades</th><th>Winners</th><th>Win%</th><th>Total PnL</th>
    </tr></thead>
    <tbody>{strat_rows}</tbody>
</table>

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    return output_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    paper_dir = ARTIFACTS_DIR / "paper"
    reports_dir = ARTIFACTS_DIR / "reports"

    print("=" * 60)
    print("  DAILY REPORT GENERATOR")
    print(f"  Date: {TODAY}")
    print(f"  Source: {paper_dir}")
    print("=" * 60)

    # Load logs
    logs = load_all_paper_logs(paper_dir)
    if not logs:
        print(f"\n  No paper trade logs found in {paper_dir}")
        print("  Run paper_trading_batch.py first to generate logs.")
        # Still generate an empty report
        logs = []

    print(f"\n  Loaded {len(logs)} log file(s):")
    for log in logs:
        print(f"    {log.get('_source_file','?')}")

    # Extract trades
    all_trades = extract_all_trades(logs)
    print(f"\n  Total trades extracted: {len(all_trades)}")

    # Compute analytics
    daily_pnl = compute_daily_pnl(all_trades)
    dates, equity = compute_cumulative_equity(daily_pnl)
    strategy_summary = compute_strategy_summary(all_trades)

    # Console output
    print_console_summary(all_trades, daily_pnl, equity, strategy_summary)

    # Generate HTML
    reports_dir.mkdir(parents=True, exist_ok=True)
    html_path = reports_dir / f"daily_{TODAY}.html"
    generate_html_report(
        all_trades=all_trades,
        daily_pnl=daily_pnl,
        dates=dates,
        equity=equity,
        strategy_summary=strategy_summary,
        output_path=str(html_path),
    )
    print(f"\n  HTML report saved: {html_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
