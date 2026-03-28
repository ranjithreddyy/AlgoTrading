#!/usr/bin/env python3
"""Paper trading CLI — simulation and live modes.

Usage:
    # Simulate using historical data:
    python scripts/run_paper_trading.py --simulate --symbol RELIANCE --interval day --bars 50

    # Live paper trading (requires market hours + valid Kite token):
    python scripts/run_paper_trading.py --symbol RELIANCE
"""

import argparse
import asyncio
import logging
import signal
import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config.settings import DATA_DIR, KITE_API_KEY, KITE_ACCESS_TOKEN
from src.core.clock import is_market_open
from src.data.storage import DataStorage
from src.strategies.base import StrategyConfig
from src.strategies.registry import StrategyRegistry, global_registry
from src.live.session_manager import SessionManager
from src.live.signal_service import SignalService
from src.live.trade_loop import TradingLoop
from src.live.monitoring import Monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("paper_trading")


def parse_args():
    p = argparse.ArgumentParser(description="Paper trading (simulation or live)")
    p.add_argument("--simulate", action="store_true", help="Replay historical data")
    p.add_argument("--symbol", default="RELIANCE", help="Trading symbol")
    p.add_argument("--exchange", default="NSE", help="Exchange (default: NSE)")
    p.add_argument("--interval", default="day", help="Bar interval (day, 15minute, etc.)")
    p.add_argument("--bars", type=int, default=50, help="Number of bars to replay in simulation")
    p.add_argument("--strategy", default="momentum_breakout", help="Strategy name")
    p.add_argument("--delay", type=float, default=0.05, help="Delay between bars in simulation (seconds)")
    return p.parse_args()


def load_strategies(strategy_name: str):
    """Discover and instantiate the requested strategy."""
    global_registry.auto_discover()
    available = global_registry.list_all()

    cls = global_registry.get(strategy_name)
    if cls is None:
        logger.error(
            "Strategy '%s' not found. Available: %s", strategy_name, available
        )
        sys.exit(1)

    config = StrategyConfig(
        name=strategy_name,
        family=getattr(cls, "__default_family__", "unknown"),
        asset_class="stock",
        params=cls(StrategyConfig(name="tmp", family="", asset_class="")).get_default_params(),
    )
    strategy = cls(config)
    return [strategy]


def print_status(loop: TradingLoop):
    """Status callback for simulation."""
    monitor = Monitor(loop)
    print(monitor.format_status_line())


def print_trade_table(trades):
    """Print a compact trade table."""
    if not trades:
        print("\n  No trades executed.")
        return

    print(f"\n  {'#':>3}  {'Side':<6} {'Entry':>10} {'Exit':>10} {'Gross PnL':>10} {'Net PnL':>10}  Reason")
    print("  " + "-" * 75)
    for i, t in enumerate(trades, 1):
        print(
            f"  {i:3d}  {t['side']:<6} {t['entry_price']:10.2f} {t['exit_price']:10.2f} "
            f"{t['gross_pnl']:+10.2f} {t['net_pnl']:+10.2f}  {t['reason']}"
        )


def print_summary(summary: dict):
    """Print final session summary."""
    print("\n" + "=" * 60)
    print("  SESSION SUMMARY")
    print("=" * 60)
    print(f"  Bars processed:   {summary.get('bars_processed', 0)}")
    print(f"  Signals generated:{summary.get('signals_generated', 0)}")
    print(f"  Total trades:     {summary.get('total_trades', 0)}")
    print(f"  Winning trades:   {summary.get('winning_trades', 0)}")
    print(f"  Losing trades:    {summary.get('losing_trades', 0)}")
    print(f"  Win rate:         {summary.get('win_rate', 0):.1%}")
    print(f"  Total PnL:        {summary.get('total_pnl', 0):+.2f}")
    print(f"  Position open:    {summary.get('position_open', False)}")
    print("=" * 60)


async def run_simulation(args):
    """Run historical data replay simulation."""
    print(f"\n  Simulation mode: {args.symbol} ({args.exchange}) / {args.interval}")
    print(f"  Strategy: {args.strategy} | Bars: {args.bars}\n")

    # Load historical data
    storage = DataStorage(str(DATA_DIR))
    df = storage.load_bars(args.symbol, args.exchange, args.interval)

    if df.empty:
        logger.error(
            "No data found for %s/%s/%s. Run data ingestion first.",
            args.exchange, args.symbol, args.interval,
        )
        sys.exit(1)

    # Take the last N bars
    df = df.tail(args.bars).reset_index(drop=True)
    print(f"  Loaded {len(df)} bars: {df['date'].iloc[0]} to {df['date'].iloc[-1]}\n")

    # Convert to list of bar dicts
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

    # Set up components
    strategies = load_strategies(args.strategy)
    session_mgr = SessionManager(config={"mode": "paper", "symbol": args.symbol})
    signal_svc = SignalService(strategies=strategies)
    loop = TradingLoop(
        session_manager=session_mgr,
        signal_service=signal_svc,
    )

    # Run
    summary = await loop.run_simulation(
        bars=bars,
        symbol=args.symbol,
        delay=args.delay,
        status_callback=print_status,
    )

    # Final output
    print_trade_table(loop.trades)
    print_summary(summary)

    monitor = Monitor(loop)
    pnl = monitor.get_pnl_summary()
    if pnl["total_pnl"] != 0:
        print(f"\n  PnL details — Best: {pnl['best_trade']:+.2f}  Worst: {pnl['worst_trade']:+.2f}  Avg: {pnl['avg_pnl']:+.2f}")

    return summary


async def run_live_paper(args):
    """Run live paper trading (market must be open)."""
    if not is_market_open():
        print("\n  Market is closed. Use --simulate to replay historical data.")
        print("  Falling back to simulation mode...\n")
        return await run_simulation(args)

    print(f"\n  Live paper trading: {args.symbol}")
    print("  Press Ctrl+C to stop.\n")

    strategies = load_strategies(args.strategy)
    session_mgr = SessionManager(config={"mode": "paper", "symbol": args.symbol})
    signal_svc = SignalService(strategies=strategies)
    loop = TradingLoop(
        session_manager=session_mgr,
        signal_service=signal_svc,
    )

    # Graceful shutdown
    stop_event = asyncio.Event()

    def handle_signal(*_):
        print("\n  Shutting down gracefully...")
        loop.stop()
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    await loop.run(symbol=args.symbol)

    print_trade_table(loop.trades)
    print_summary(loop.get_summary())


def main():
    args = parse_args()

    if args.simulate:
        asyncio.run(run_simulation(args))
    else:
        asyncio.run(run_live_paper(args))


if __name__ == "__main__":
    main()
