"""Aggregate raw ticks into OHLCV bars."""

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Bar:
    """A single OHLCV bar."""
    timestamp: float  # epoch of bar open
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0
    tick_count: int = 0

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
        }


class TickAggregator:
    """Aggregate ticks into fixed-interval OHLCV bars.

    Args:
        interval_seconds: Bar interval in seconds (default 60 = 1 minute).
    """

    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self._current_bar: Optional[Bar] = None
        self._completed_bar: Optional[Bar] = None
        self._bar_start: float = 0.0

    def _bar_boundary(self, ts: float) -> float:
        """Return the start of the interval that ``ts`` belongs to."""
        return ts - (ts % self.interval_seconds)

    def on_tick(self, tick: dict) -> Optional[Bar]:
        """Process an incoming tick.

        Expected tick keys: ``last_price`` (float), ``volume`` (float, optional),
        ``timestamp`` (float epoch, optional – defaults to ``time.time()``).

        Returns:
            The just-completed Bar if the tick caused a new interval to start,
            otherwise None.
        """
        price = tick.get("last_price", tick.get("close", 0.0))
        vol = tick.get("volume", 0)
        ts = tick.get("timestamp", time.time())

        boundary = self._bar_boundary(ts)
        completed = None

        if self._current_bar is None:
            # First tick ever
            self._bar_start = boundary
            self._current_bar = Bar(
                timestamp=boundary,
                open=price, high=price, low=price, close=price,
                volume=vol, tick_count=1,
            )
        elif boundary > self._bar_start:
            # New interval -> complete previous bar
            completed = self._current_bar
            self._completed_bar = completed
            self._bar_start = boundary
            self._current_bar = Bar(
                timestamp=boundary,
                open=price, high=price, low=price, close=price,
                volume=vol, tick_count=1,
            )
        else:
            # Same interval -> update current bar
            bar = self._current_bar
            bar.high = max(bar.high, price)
            bar.low = min(bar.low, price)
            bar.close = price
            bar.volume += vol
            bar.tick_count += 1

        return completed

    def get_completed_bar(self) -> Optional[Bar]:
        """Return the most recently completed bar, or None."""
        return self._completed_bar

    def get_current_bar(self) -> Optional[Bar]:
        """Return the partial bar currently in progress."""
        return self._current_bar

    def reset(self) -> None:
        """Reset all state."""
        self._current_bar = None
        self._completed_bar = None
        self._bar_start = 0.0
