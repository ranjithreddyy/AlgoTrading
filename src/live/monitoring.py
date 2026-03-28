"""Live monitoring for the trading loop."""

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.clock import current_ist


class Monitor:
    """Provides status, PnL, position, and alert information from a TradingLoop."""

    def __init__(self, trade_loop):
        self.trade_loop = trade_loop
        self._alerts: List[Dict[str, str]] = []

    def add_alert(self, level: str, message: str) -> None:
        """Add an alert (level: 'info', 'warning', 'error')."""
        self._alerts.append({
            "level": level,
            "message": message,
            "time": current_ist().isoformat(),
        })

    def get_status(self) -> Dict[str, Any]:
        """Return comprehensive live metrics."""
        loop = self.trade_loop
        sm = loop.session_manager

        status = {
            "timestamp": current_ist().isoformat(),
            "session": sm.get_session_status(),
            "trading": loop.get_summary(),
            "position": loop.position,
        }

        if loop.feed:
            status["feed"] = loop.feed.get_stats()

        return status

    def get_pnl_summary(self) -> Dict[str, Any]:
        """Return PnL breakdown."""
        trades = self.trade_loop.trades
        if not trades:
            return {
                "total_pnl": 0.0,
                "gross_pnl": 0.0,
                "total_cost": 0.0,
                "best_trade": 0.0,
                "worst_trade": 0.0,
                "avg_pnl": 0.0,
            }

        pnls = [t["net_pnl"] for t in trades]
        return {
            "total_pnl": round(sum(pnls), 2),
            "gross_pnl": round(sum(t["gross_pnl"] for t in trades), 2),
            "total_cost": round(sum(t["cost"] for t in trades), 2),
            "best_trade": round(max(pnls), 2),
            "worst_trade": round(min(pnls), 2),
            "avg_pnl": round(sum(pnls) / len(pnls), 2),
        }

    def get_active_positions(self) -> List[Dict]:
        """Return list of currently open positions."""
        pos = self.trade_loop.position
        if pos is None:
            return []
        return [pos]

    def get_recent_trades(self, n: int = 10) -> List[Dict]:
        """Return the last N completed trades."""
        return self.trade_loop.trades[-n:]

    def get_alerts(self) -> List[Dict[str, str]]:
        """Return all alert messages."""
        return self._alerts[-50:]  # keep last 50

    def format_status_line(self) -> str:
        """One-line status string for terminal output."""
        loop = self.trade_loop
        sm = loop.session_manager
        pnl = sum(t["net_pnl"] for t in loop.trades)
        pos_str = "FLAT"
        if loop.position:
            pos_str = f"{loop.position['side'].upper()} @ {loop.position['entry']:.2f}"

        return (
            f"[{current_ist().strftime('%H:%M:%S')}] "
            f"Bars: {loop.bars_processed} | "
            f"Signals: {loop.signals_generated} | "
            f"Trades: {len(loop.trades)} | "
            f"PnL: {pnl:+.2f} | "
            f"Pos: {pos_str} | "
            f"{'ACTIVE' if sm.is_session_active() else 'ENDED'}"
        )
