"""HTML report generation for backtest results."""

import base64
import io
import math
import os
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import numpy as np

from src.strategies.base import BacktestResult


def _encode_figure_base64(fig) -> str:
    """Render a matplotlib figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# Existing charts (preserved + enhanced)
# ---------------------------------------------------------------------------

def _build_equity_chart(results: List[BacktestResult]) -> str:
    """Build an equity curve chart comparing all strategies."""
    fig, ax = plt.subplots(figsize=(12, 5))
    for r in results:
        if r.equity_curve:
            ax.plot(r.equity_curve, label=r.strategy_name, linewidth=1.2)
    ax.set_title("Equity Curves")
    ax.set_xlabel("Bar index")
    ax.set_ylabel("Cumulative PnL")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    return _encode_figure_base64(fig)


def _build_monthly_pnl(results: List[BacktestResult]) -> Optional[str]:
    """Build a monthly PnL bar chart if trade date info is available."""
    monthly_data: Dict[str, Dict[str, float]] = {}
    has_dates = False

    for r in results:
        for t in r.trades:
            exit_date = t.get("exit_date", "")
            if not exit_date:
                continue
            has_dates = True
            try:
                month_key = exit_date[:7]  # YYYY-MM
            except Exception:
                continue
            if r.strategy_name not in monthly_data:
                monthly_data[r.strategy_name] = {}
            monthly_data[r.strategy_name][month_key] = (
                monthly_data[r.strategy_name].get(month_key, 0.0) + t["net_pnl"]
            )

    if not has_dates or not monthly_data:
        return None

    all_months = sorted(
        set(m for strat in monthly_data.values() for m in strat.keys())
    )
    if not all_months:
        return None

    fig, ax = plt.subplots(figsize=(12, 5))
    n_strats = len(monthly_data)
    width = 0.8 / max(n_strats, 1)
    x_indices = list(range(len(all_months)))

    for i, (strat_name, months) in enumerate(monthly_data.items()):
        values = [months.get(m, 0.0) for m in all_months]
        offsets = [x + i * width for x in x_indices]
        colors = ["green" if v >= 0 else "red" for v in values]
        ax.bar(offsets, values, width=width, label=strat_name, color=colors, alpha=0.7)

    ax.set_xticks([x + width * (n_strats - 1) / 2 for x in x_indices])
    ax.set_xticklabels(all_months, rotation=45, ha="right", fontsize=7)
    ax.set_title("Monthly PnL Breakdown")
    ax.set_ylabel("Net PnL")
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _encode_figure_base64(fig)


# ---------------------------------------------------------------------------
# New charts
# ---------------------------------------------------------------------------

def _build_rolling_sharpe(results: List[BacktestResult], window: int = 60) -> Optional[str]:
    """Rolling Sharpe ratio chart (rolling 60-bar window on the equity curve)."""
    has_data = any(len(r.equity_curve) > window for r in results)
    if not has_data:
        return None

    fig, ax = plt.subplots(figsize=(12, 5))

    for r in results:
        eq = r.equity_curve
        if len(eq) <= window:
            continue
        # Daily returns from equity curve
        returns = [eq[i] - eq[i - 1] for i in range(1, len(eq))]
        if len(returns) < window:
            continue

        rolling_sharpe = []
        for i in range(window, len(returns) + 1):
            window_rets = returns[i - window:i]
            mean = sum(window_rets) / window
            var = sum((x - mean) ** 2 for x in window_rets) / window
            std = math.sqrt(var) if var > 0 else 1e-9
            sharpe = (mean / std) * math.sqrt(252)
            rolling_sharpe.append(sharpe)

        x = list(range(window, len(returns) + 1))
        ax.plot(x, rolling_sharpe, label=r.strategy_name, linewidth=1.1, alpha=0.85)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axhline(1.0, color="green", linewidth=0.6, linestyle=":", alpha=0.5)
    ax.axhline(-1.0, color="red", linewidth=0.6, linestyle=":", alpha=0.5)
    ax.set_title(f"Rolling {window}-Bar Sharpe Ratio")
    ax.set_xlabel("Bar index")
    ax.set_ylabel(f"Sharpe ({window}-bar rolling)")
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _encode_figure_base64(fig)


def _build_drawdown_waterfall(results: List[BacktestResult]) -> Optional[str]:
    """Drawdown waterfall chart — underwater equity curve per strategy."""
    has_data = any(len(r.equity_curve) > 2 for r in results)
    if not has_data:
        return None

    fig, ax = plt.subplots(figsize=(12, 5))

    for r in results:
        eq = r.equity_curve
        if len(eq) < 2:
            continue
        peak = eq[0]
        drawdowns = []
        for v in eq:
            if v > peak:
                peak = v
            drawdowns.append(v - peak)  # always <= 0

        ax.fill_between(
            range(len(drawdowns)),
            drawdowns,
            0,
            alpha=0.3,
            label=r.strategy_name,
        )
        ax.plot(drawdowns, linewidth=0.8, alpha=0.7)

    ax.set_title("Drawdown Waterfall (Underwater Equity)")
    ax.set_xlabel("Bar index")
    ax.set_ylabel("Drawdown from peak")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.legend(fontsize=8, loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return _encode_figure_base64(fig)


def _build_monthly_heatmap(results: List[BacktestResult]) -> Optional[str]:
    """Monthly PnL heatmap (months × strategies) if enough data."""
    # Collect monthly PnL per strategy
    monthly_data: Dict[str, Dict[str, float]] = {}
    for r in results:
        for t in r.trades:
            exit_date = t.get("exit_date", "")
            if not exit_date:
                continue
            try:
                month_key = str(exit_date)[:7]
            except Exception:
                continue
            if r.strategy_name not in monthly_data:
                monthly_data[r.strategy_name] = {}
            monthly_data[r.strategy_name][month_key] = (
                monthly_data[r.strategy_name].get(month_key, 0.0) + t["net_pnl"]
            )

    if not monthly_data:
        return None

    all_months = sorted(set(m for s in monthly_data.values() for m in s))
    if len(all_months) < 2:
        return None

    strat_names = list(monthly_data.keys())
    matrix = []
    for strat in strat_names:
        row = [monthly_data[strat].get(m, 0.0) for m in all_months]
        matrix.append(row)

    matrix_arr = matrix
    max_abs = max(abs(v) for row in matrix_arr for v in row) or 1.0

    fig, ax = plt.subplots(figsize=(max(8, len(all_months) * 0.8), max(3, len(strat_names) * 0.7)))
    im = ax.imshow(
        matrix_arr, cmap="RdYlGn", aspect="auto",
        vmin=-max_abs, vmax=max_abs
    )
    ax.set_xticks(range(len(all_months)))
    ax.set_xticklabels(all_months, rotation=45, ha="right", fontsize=7)
    ax.set_yticks(range(len(strat_names)))
    ax.set_yticklabels(strat_names, fontsize=8)
    ax.set_title("Monthly PnL Heatmap (strategy vs month)")
    plt.colorbar(im, ax=ax, label="Net PnL")

    for i in range(len(strat_names)):
        for j in range(len(all_months)):
            val = matrix_arr[i][j]
            ax.text(
                j, i, f"{val:.0f}", ha="center", va="center",
                fontsize=6, color="white" if abs(val) > max_abs * 0.6 else "black"
            )

    fig.tight_layout()
    return _encode_figure_base64(fig)


def _build_win_loss_streak(results: List[BacktestResult]) -> Optional[str]:
    """Win/loss streak analysis bar chart."""
    has_trades = any(r.total_trades > 1 for r in results)
    if not has_trades:
        return None

    strat_names = []
    max_win_streaks = []
    max_loss_streaks = []

    for r in results:
        if not r.trades:
            continue
        strat_names.append(r.strategy_name)
        max_win = max_loss = cur_win = cur_loss = 0
        for t in r.trades:
            if t["net_pnl"] > 0:
                cur_win += 1
                cur_loss = 0
                max_win = max(max_win, cur_win)
            else:
                cur_loss += 1
                cur_win = 0
                max_loss = max(max_loss, cur_loss)
        max_win_streaks.append(max_win)
        max_loss_streaks.append(max_loss)

    if not strat_names:
        return None

    x = list(range(len(strat_names)))
    width = 0.35

    fig, ax = plt.subplots(figsize=(max(8, len(strat_names) * 1.2), 5))
    ax.bar([xi - width / 2 for xi in x], max_win_streaks, width, label="Max Win Streak",
           color="#2ecc71", alpha=0.8)
    ax.bar([xi + width / 2 for xi in x], max_loss_streaks, width, label="Max Loss Streak",
           color="#e74c3c", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(strat_names, rotation=30, ha="right", fontsize=8)
    ax.set_title("Max Win/Loss Streak per Strategy")
    ax.set_ylabel("Consecutive Trades")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    return _encode_figure_base64(fig)


def _collect_best_worst_trades(
    results: List[BacktestResult], n: int = 5
) -> Tuple[List[dict], List[dict]]:
    """Collect top-N best and worst trades across all strategies."""
    all_trades = []
    for r in results:
        for t in r.trades:
            all_trades.append({**t, "strategy": r.strategy_name})

    if not all_trades:
        return [], []

    sorted_by_pnl = sorted(all_trades, key=lambda t: t["net_pnl"], reverse=True)
    best = sorted_by_pnl[:n]
    worst = sorted_by_pnl[-n:][::-1]  # worst first
    return best, worst


# ---------------------------------------------------------------------------
# Per-symbol breakdown (new)
# ---------------------------------------------------------------------------

def _build_per_symbol_table(results: List[BacktestResult]) -> str:
    """Build an HTML table showing per-symbol summary (if symbol info is present)."""
    # Group by symbol if 'symbol' key exists in trades
    symbol_data: Dict[str, Dict[str, float]] = defaultdict(lambda: {"pnl": 0.0, "trades": 0, "wins": 0})
    for r in results:
        for t in r.trades:
            sym = t.get("symbol", "UNKNOWN")
            symbol_data[sym]["pnl"] += t["net_pnl"]
            symbol_data[sym]["trades"] += 1
            if t["net_pnl"] > 0:
                symbol_data[sym]["wins"] += 1

    if not symbol_data or (len(symbol_data) == 1 and "UNKNOWN" in symbol_data):
        return ""  # No symbol-level info

    rows = ""
    for sym, d in sorted(symbol_data.items()):
        win_rate = d["wins"] / d["trades"] * 100 if d["trades"] else 0
        cls = "viable" if d["pnl"] > 0 else "not-viable"
        rows += f"""
        <tr class="{cls}">
            <td>{sym}</td>
            <td>{d['trades']}</td>
            <td>{win_rate:.1f}%</td>
            <td>{d['pnl']:+.2f}</td>
        </tr>"""

    if not rows:
        return ""

    return f"""
    <h2>Per-Symbol Breakdown</h2>
    <table>
        <thead>
            <tr><th>Symbol</th><th>Trades</th><th>Win Rate</th><th>Net PnL</th></tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>"""


# ---------------------------------------------------------------------------
# Main report generator
# ---------------------------------------------------------------------------

def generate_html_report(
    results: List[BacktestResult],
    output_path: str,
    title: str = "Backtest Report",
) -> str:
    """Generate an HTML comparison report and save to output_path.

    Args:
        results: List of BacktestResult objects to compare.
        output_path: File path to write the HTML report.
        title: Report title.

    Returns:
        The output_path where the report was saved.
    """
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Sort by Sharpe for leaderboard
    ranked = sorted(results, key=lambda r: r.sharpe_ratio, reverse=True)

    # Build core charts
    equity_img = _build_equity_chart(ranked)
    monthly_img = _build_monthly_pnl(ranked)

    # Build new enhanced charts
    rolling_sharpe_img = _build_rolling_sharpe(ranked, window=60)
    drawdown_img = _build_drawdown_waterfall(ranked)
    heatmap_img = _build_monthly_heatmap(ranked)
    streak_img = _build_win_loss_streak(ranked)

    # Per-symbol breakdown HTML
    per_symbol_section = _build_per_symbol_table(ranked)

    # Best/worst trades
    best_trades, worst_trades = _collect_best_worst_trades(ranked, n=5)

    # --- Leaderboard table ---
    leaderboard_rows = ""
    for i, r in enumerate(ranked, 1):
        viable = r.net_pnl > 0
        row_class = "viable" if viable else "not-viable"
        leaderboard_rows += f"""
        <tr class="{row_class}">
            <td>{i}</td>
            <td>{r.strategy_name}</td>
            <td>{r.total_trades}</td>
            <td>{r.win_rate:.1%}</td>
            <td>{r.net_pnl:.2f}</td>
            <td>{r.sharpe_ratio:.4f}</td>
            <td>{r.profit_factor:.4f}</td>
            <td>{r.max_drawdown:.2f}</td>
            <td>{r.avg_trade_pnl:.2f}</td>
        </tr>"""

    # --- Strategy cards ---
    cards_html = ""
    for r in ranked:
        n_winners = r.winning_trades
        n_losers = r.losing_trades
        avg_win = 0.0
        avg_loss = 0.0
        if r.trades:
            wins = [t["net_pnl"] for t in r.trades if t["net_pnl"] > 0]
            losses = [t["net_pnl"] for t in r.trades if t["net_pnl"] <= 0]
            avg_win = sum(wins) / len(wins) if wins else 0.0
            avg_loss = sum(losses) / len(losses) if losses else 0.0

        params_str = ", ".join(f"{k}={v}" for k, v in r.params.items()) if r.params else "defaults"

        cards_html += f"""
        <div class="card">
            <h3>{r.strategy_name}</h3>
            <p class="params">Params: {params_str}</p>
            <table class="stats">
                <tr><td>Total Trades</td><td>{r.total_trades}</td></tr>
                <tr><td>Win / Loss</td><td>{n_winners} / {n_losers}</td></tr>
                <tr><td>Win Rate</td><td>{r.win_rate:.1%}</td></tr>
                <tr><td>Gross PnL</td><td>{r.gross_pnl:.2f}</td></tr>
                <tr><td>Net PnL</td><td>{r.net_pnl:.2f}</td></tr>
                <tr><td>Sharpe Ratio</td><td>{r.sharpe_ratio:.4f}</td></tr>
                <tr><td>Profit Factor</td><td>{r.profit_factor:.4f}</td></tr>
                <tr><td>Max Drawdown</td><td>{r.max_drawdown:.2f}</td></tr>
                <tr><td>Avg Trade PnL</td><td>{r.avg_trade_pnl:.2f}</td></tr>
                <tr><td>Avg Win</td><td>{avg_win:.2f}</td></tr>
                <tr><td>Avg Loss</td><td>{avg_loss:.2f}</td></tr>
            </table>
        </div>"""

    # --- Trade statistics table ---
    trade_stats_rows = ""
    for r in ranked:
        if not r.trades:
            continue
        pnls = [t["net_pnl"] for t in r.trades]
        max_win = max(pnls) if pnls else 0
        max_loss = min(pnls) if pnls else 0
        trade_stats_rows += f"""
        <tr>
            <td>{r.strategy_name}</td>
            <td>{r.total_trades}</td>
            <td>{r.winning_trades}</td>
            <td>{r.losing_trades}</td>
            <td>{max_win:.2f}</td>
            <td>{max_loss:.2f}</td>
            <td>{r.avg_trade_pnl:.2f}</td>
        </tr>"""

    # --- Best trades table ---
    best_rows = ""
    for t in best_trades:
        best_rows += f"""
        <tr class="viable">
            <td>{t.get('strategy', '')}</td>
            <td>{t.get('symbol', '')}</td>
            <td>{t.get('side', '')}</td>
            <td>{t.get('entry_date', '')[:10]}</td>
            <td>{t.get('exit_date', '')[:10]}</td>
            <td>{t.get('entry_price', 0):.2f}</td>
            <td>{t.get('exit_price', 0):.2f}</td>
            <td>{t.get('net_pnl', 0):+.2f}</td>
        </tr>"""

    # --- Worst trades table ---
    worst_rows = ""
    for t in worst_trades:
        worst_rows += f"""
        <tr class="not-viable">
            <td>{t.get('strategy', '')}</td>
            <td>{t.get('symbol', '')}</td>
            <td>{t.get('side', '')}</td>
            <td>{t.get('entry_date', '')[:10]}</td>
            <td>{t.get('exit_date', '')[:10]}</td>
            <td>{t.get('entry_price', 0):.2f}</td>
            <td>{t.get('exit_price', 0):.2f}</td>
            <td>{t.get('net_pnl', 0):+.2f}</td>
        </tr>"""

    best_worst_header = """
        <th>Strategy</th><th>Symbol</th><th>Side</th>
        <th>Entry Date</th><th>Exit Date</th>
        <th>Entry</th><th>Exit</th><th>Net PnL</th>"""

    # --- Monthly PnL section ---
    monthly_section = ""
    if monthly_img:
        monthly_section = f"""
        <h2>Monthly PnL Breakdown</h2>
        <img src="data:image/png;base64,{monthly_img}" alt="Monthly PnL" class="chart">
        """

    # --- Rolling Sharpe section ---
    rolling_sharpe_section = ""
    if rolling_sharpe_img:
        rolling_sharpe_section = f"""
        <h2>Rolling 60-Bar Sharpe Ratio</h2>
        <img src="data:image/png;base64,{rolling_sharpe_img}" alt="Rolling Sharpe" class="chart">
        """

    # --- Drawdown waterfall section ---
    drawdown_section = ""
    if drawdown_img:
        drawdown_section = f"""
        <h2>Drawdown Waterfall</h2>
        <img src="data:image/png;base64,{drawdown_img}" alt="Drawdown Waterfall" class="chart">
        """

    # --- Monthly heatmap section ---
    heatmap_section = ""
    if heatmap_img:
        heatmap_section = f"""
        <h2>Monthly PnL Heatmap</h2>
        <img src="data:image/png;base64,{heatmap_img}" alt="Monthly Heatmap" class="chart">
        """

    # --- Streak analysis section ---
    streak_section = ""
    if streak_img:
        streak_section = f"""
        <h2>Win / Loss Streak Analysis</h2>
        <img src="data:image/png;base64,{streak_img}" alt="Streak Analysis" class="chart">
        """

    # --- Best/worst trades section ---
    best_worst_section = ""
    if best_trades or worst_trades:
        best_worst_section = f"""
        <h2>Best Trades (top 5)</h2>
        <table>
            <thead><tr>{best_worst_header}</tr></thead>
            <tbody>{best_rows}</tbody>
        </table>
        <h2>Worst Trades (bottom 5)</h2>
        <table>
            <thead><tr>{best_worst_header}</tr></thead>
            <tbody>{worst_rows}</tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background: #f5f5f5;
        color: #333;
    }}
    h1 {{ color: #1a1a2e; border-bottom: 3px solid #16213e; padding-bottom: 10px; }}
    h2 {{ color: #16213e; margin-top: 30px; }}
    .timestamp {{ color: #666; font-size: 0.9em; }}
    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 15px 0;
        background: white;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}
    th {{
        background: #16213e;
        color: white;
        padding: 10px 12px;
        text-align: left;
        font-size: 0.85em;
    }}
    td {{
        padding: 8px 12px;
        border-bottom: 1px solid #eee;
        font-size: 0.85em;
    }}
    tr:hover {{ background: #f0f4ff; }}
    tr.viable td {{ color: #155724; }}
    tr.not-viable td {{ color: #721c24; }}
    .cards {{ display: flex; flex-wrap: wrap; gap: 15px; margin: 15px 0; }}
    .card {{
        background: white;
        border-radius: 8px;
        padding: 15px;
        flex: 1 1 300px;
        max-width: 380px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    .card h3 {{ margin: 0 0 8px 0; color: #16213e; }}
    .card .params {{ font-size: 0.8em; color: #666; margin: 0 0 10px 0; word-break: break-all; }}
    .card .stats {{ box-shadow: none; }}
    .card .stats td {{ padding: 4px 8px; font-size: 0.82em; }}
    .chart {{ width: 100%; max-width: 1100px; margin: 15px 0; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="timestamp">Generated: {timestamp}</p>

<h2>Leaderboard (ranked by Sharpe Ratio)</h2>
<table>
    <thead>
        <tr>
            <th>Rank</th><th>Strategy</th><th>Trades</th><th>Win Rate</th>
            <th>Net PnL</th><th>Sharpe</th><th>Profit Factor</th>
            <th>Max DD</th><th>Avg Trade</th>
        </tr>
    </thead>
    <tbody>
        {leaderboard_rows}
    </tbody>
</table>

{per_symbol_section}

<h2>Equity Curves</h2>
<img src="data:image/png;base64,{equity_img}" alt="Equity Curves" class="chart">

{rolling_sharpe_section}

{drawdown_section}

<h2>Strategy Details</h2>
<div class="cards">
    {cards_html}
</div>

<h2>Trade Statistics</h2>
<table>
    <thead>
        <tr>
            <th>Strategy</th><th>Total</th><th>Winners</th><th>Losers</th>
            <th>Best Trade</th><th>Worst Trade</th><th>Avg Trade</th>
        </tr>
    </thead>
    <tbody>
        {trade_stats_rows}
    </tbody>
</table>

{streak_section}

{best_worst_section}

{monthly_section}

{heatmap_section}

</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)

    return output_path
