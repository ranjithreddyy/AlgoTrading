"""Main trading loop for live / paper trading."""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.core.clock import current_ist, is_market_open, time_to_close
from src.data.tick_aggregator import Bar, TickAggregator
from src.live.session_manager import SessionManager
from src.live.signal_service import Signal, SignalService

logger = logging.getLogger(__name__)


class TradingLoop:
    """Orchestrates the tick -> bar -> signal -> execution pipeline.

    Works in two modes:
    1. Live: receives ticks from a WebSocket feed.
    2. Simulate: replays historical bars directly.
    """

    def __init__(
        self,
        session_manager: SessionManager,
        signal_service: SignalService,
        broker: Any = None,
        feed: Any = None,
        aggregator: Optional[TickAggregator] = None,
    ):
        self.session_manager = session_manager
        self.signal_service = signal_service
        self.broker = broker
        self.feed = feed
        self.aggregator = aggregator or TickAggregator(interval_seconds=60)

        self.bars_processed: int = 0
        self.signals_generated: int = 0
        self.orders_placed: int = 0
        self.trades: List[Dict] = []
        self.position: Optional[Dict] = None  # {"side","entry","entry_date"}
        self._running: bool = False
        self._pnl: float = 0.0

    # ------------------------------------------------------------------
    # Simulation mode (replay historical bars)
    # ------------------------------------------------------------------

    async def run_simulation(
        self,
        bars: List[dict],
        symbol: str,
        delay: float = 0.05,
        status_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Replay a list of historical bars as if they were live.

        Args:
            bars: List of bar dicts with date/open/high/low/close/volume.
            symbol: Instrument symbol.
            delay: Seconds to sleep between bars (for visual effect).
            status_callback: Optional callable(loop) invoked every N bars.

        Returns:
            Summary dict.
        """
        self._running = True
        self.session_manager.start_session()
        logger.info("Starting simulation with %d bars for %s", len(bars), symbol)

        for i, bar in enumerate(bars):
            if not self._running:
                break

            self._process_bar(symbol, bar)
            self.bars_processed += 1

            if status_callback and (i + 1) % 10 == 0:
                status_callback(self)

            if delay > 0:
                await asyncio.sleep(delay)

        # Force-close open position at the end
        if self.position is not None and bars:
            self._force_close(symbol, bars[-1])

        summary = self.session_manager.end_session()
        summary.update(self.get_summary())
        self._running = False
        return summary

    # ------------------------------------------------------------------
    # Live mode
    # ------------------------------------------------------------------

    async def run(self, symbol: str) -> None:
        """Main async loop for live trading.

        Ticks arrive via the feed's callback which calls on_tick().
        This loop just monitors health and handles shutdown.
        """
        self._running = True
        self.session_manager.start_session()
        logger.info("Trading loop started for %s", symbol)

        try:
            while self._running:
                # Check market close
                ttc = time_to_close()
                if ttc.total_seconds() <= 0 and not is_market_open():
                    logger.info("Market closed, ending session")
                    break

                # Health check every 30s
                await asyncio.sleep(30)

                if self.feed and not self.feed.is_healthy():
                    logger.warning("Feed unhealthy; reconnects=%d", self.feed.reconnect_count)

        except asyncio.CancelledError:
            logger.info("Trading loop cancelled")
        finally:
            if self.position is not None:
                logger.info("Flattening open position on shutdown")
            self.session_manager.end_session()
            self._running = False

    def on_tick(self, ticks: list) -> None:
        """Process incoming ticks (called by the feed callback)."""
        for tick in ticks:
            completed_bar = self.aggregator.on_tick(tick)
            if completed_bar is not None:
                bar_dict = completed_bar.as_dict()
                symbol = tick.get("tradingsymbol", "UNKNOWN")
                self._process_bar(symbol, bar_dict)
                self.bars_processed += 1

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def _process_bar(self, symbol: str, bar: dict) -> None:
        """Run the signal pipeline on one completed bar."""
        # Update strategy contexts with current position
        for strategy in self.signal_service.strategies:
            self.signal_service.set_context(
                strategy.config.name,
                {"position": self.position},
            )

        signals = self.signal_service.on_bar(symbol, bar)
        self.signals_generated += len(signals)

        for sig in signals:
            if not sig.accepted:
                continue
            self._execute_signal(sig, bar)

    def _execute_signal(self, signal: Signal, bar: dict) -> None:
        """Execute a signal: open or close positions via the broker."""
        action = signal.action

        if self.position is None:
            # Open position
            side = "long" if action == "buy" else "short"
            self.position = {
                "side": side,
                "entry": signal.price,
                "entry_date": bar.get("date", ""),
                "symbol": signal.symbol,
            }
            self.orders_placed += 1
            logger.info(
                "OPEN %s %s @ %.2f (%s)",
                side.upper(), signal.symbol, signal.price, signal.reason,
            )
        else:
            # Close if opposite signal
            should_close = (
                (self.position["side"] == "long" and action == "sell")
                or (self.position["side"] == "short" and action == "buy")
            )
            if should_close:
                self._close_position(signal.price, bar.get("date", ""), signal.reason)

    def _close_position(self, exit_price: float, exit_date: str, reason: str) -> None:
        """Close current position and record trade."""
        pos = self.position
        if pos is None:
            return

        entry = pos["entry"]
        if pos["side"] == "long":
            gross_pnl = exit_price - entry
        else:
            gross_pnl = entry - exit_price

        # Simplified cost (0.04% round trip)
        cost = (entry + exit_price) * 0.0002
        net_pnl = gross_pnl - cost

        trade = {
            "symbol": pos.get("symbol", ""),
            "side": pos["side"],
            "entry_price": entry,
            "exit_price": exit_price,
            "entry_date": pos["entry_date"],
            "exit_date": exit_date,
            "gross_pnl": round(gross_pnl, 2),
            "cost": round(cost, 2),
            "net_pnl": round(net_pnl, 2),
            "reason": reason,
        }
        self.trades.append(trade)
        self.session_manager.trades.append(trade)
        self._pnl += net_pnl
        self.orders_placed += 1

        logger.info(
            "CLOSE %s %s @ %.2f | PnL: %.2f (net: %.2f) | %s",
            pos["side"].upper(), pos.get("symbol", ""), exit_price,
            gross_pnl, net_pnl, reason,
        )
        self.position = None

    def _force_close(self, symbol: str, last_bar: dict) -> None:
        """Force-close any open position at last bar's close."""
        if self.position:
            self._close_position(
                last_bar["close"],
                str(last_bar.get("date", "")),
                "session_end_flatten",
            )

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Signal the loop to stop."""
        self._running = False

    def get_summary(self) -> Dict[str, Any]:
        """Return a summary of the trading session."""
        winners = [t for t in self.trades if t["net_pnl"] > 0]
        losers = [t for t in self.trades if t["net_pnl"] <= 0]
        total_pnl = sum(t["net_pnl"] for t in self.trades)

        return {
            "bars_processed": self.bars_processed,
            "signals_generated": self.signals_generated,
            "orders_placed": self.orders_placed,
            "total_trades": len(self.trades),
            "winning_trades": len(winners),
            "losing_trades": len(losers),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(len(winners) / len(self.trades), 4) if self.trades else 0.0,
            "position_open": self.position is not None,
        }
