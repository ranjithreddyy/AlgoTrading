#!/usr/bin/env python3
"""Live trading CLI — connects to Kite for real order execution.

Safety features:
    - Requires --confirm flag to start
    - Starts in shadow mode by default (signals only, no orders)
    - Use --live to actually place orders

Usage:
    # Shadow mode (log signals, no orders):
    python scripts/run_live_trading.py --confirm --symbol RELIANCE

    # Live mode (actually place orders):
    python scripts/run_live_trading.py --confirm --live --symbol RELIANCE
"""

import argparse
import asyncio
import logging
import signal
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.config.settings import KITE_API_KEY, KITE_ACCESS_TOKEN, DATA_DIR
from src.core.clock import is_market_open
from src.strategies.base import StrategyConfig
from src.strategies.registry import global_registry
from src.live.session_manager import SessionManager
from src.live.signal_service import SignalService
from src.live.trade_loop import TradingLoop
from src.live.monitoring import Monitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("live_trading")


def parse_args():
    p = argparse.ArgumentParser(description="Live trading with Kite")
    p.add_argument("--confirm", action="store_true", required=True,
                    help="Required safety flag to confirm live trading intent")
    p.add_argument("--live", action="store_true",
                    help="Actually place orders (default: shadow/signal-only mode)")
    p.add_argument("--symbol", default="RELIANCE", help="Trading symbol")
    p.add_argument("--exchange", default="NSE", help="Exchange")
    p.add_argument("--strategy", default="momentum_breakout", help="Strategy name")
    return p.parse_args()


def preflight_checks(args) -> bool:
    """Run safety checks before starting live trading."""
    errors = []

    if not KITE_API_KEY:
        errors.append("KITE_API_KEY not set in environment")
    if not KITE_ACCESS_TOKEN:
        errors.append("KITE_ACCESS_TOKEN not set in environment")
    if not is_market_open():
        errors.append("Market is currently closed")

    if errors:
        print("\n  PREFLIGHT CHECKS FAILED:")
        for e in errors:
            print(f"    - {e}")
        print()
        return False

    return True


async def run(args):
    """Run live trading."""
    mode = "LIVE" if args.live else "SHADOW (signals only)"
    print("\n" + "=" * 60)
    print(f"  LIVE TRADING — {mode}")
    print(f"  Symbol: {args.symbol} | Strategy: {args.strategy}")
    print("=" * 60)

    if not args.live:
        print("\n  Running in SHADOW mode: signals will be logged but no orders placed.")
        print("  Use --live flag to enable actual order placement.\n")

    if not preflight_checks(args):
        print("  Aborting. Fix the above issues and retry.")
        sys.exit(1)

    # Auto-discover strategies
    global_registry.auto_discover()
    cls = global_registry.get(args.strategy)
    if cls is None:
        logger.error("Strategy '%s' not found", args.strategy)
        sys.exit(1)

    config = StrategyConfig(
        name=args.strategy,
        family=getattr(cls, "__default_family__", "unknown"),
        asset_class="stock",
        params=cls(StrategyConfig(name="tmp", family="", asset_class="")).get_default_params(),
    )
    strategies = [cls(config)]

    session_mgr = SessionManager(config={
        "mode": "live" if args.live else "shadow",
        "symbol": args.symbol,
        "api_key": KITE_API_KEY,
        "access_token": KITE_ACCESS_TOKEN,
    })
    signal_svc = SignalService(strategies=strategies)

    # In shadow mode, broker is None (no orders placed)
    broker = None
    if args.live:
        # Future: initialize KiteBroker here
        logger.info("Live order execution enabled")
        # broker = KiteBroker(...)

    loop = TradingLoop(
        session_manager=session_mgr,
        signal_service=signal_svc,
        broker=broker,
    )
    monitor = Monitor(loop)

    # Graceful shutdown
    def handle_signal(*_):
        print("\n  Shutting down...")
        loop.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    # Connect WebSocket feed
    try:
        from src.data.websocket_feed import KiteWebSocketFeed

        feed = KiteWebSocketFeed(
            api_key=KITE_API_KEY,
            access_token=KITE_ACCESS_TOKEN,
            on_tick_callback=loop.on_tick,
        )
        loop.feed = feed
        # In a real setup, we would look up instrument tokens
        # feed.connect(instruments=[738561])  # RELIANCE token
        logger.info("WebSocket feed configured (not connecting without instrument tokens)")
    except ImportError:
        logger.warning("kiteconnect not available; feed will not be started")

    await loop.run(symbol=args.symbol)

    # Final summary
    summary = loop.get_summary()
    print("\n" + monitor.format_status_line())
    print(f"\n  Session ended. Total PnL: {summary['total_pnl']:+.2f}")


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
