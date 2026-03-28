"""WebSocket data feed wrapping KiteTicker with resilience."""

import logging
import time
from typing import Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class KiteWebSocketFeed:
    """Wraps KiteTicker with exponential backoff reconnect and health tracking."""

    MAX_BACKOFF = 30  # seconds
    HEALTH_TIMEOUT = 60  # seconds without a tick = unhealthy

    def __init__(
        self,
        api_key: str,
        access_token: str,
        on_tick_callback: Callable,
    ):
        self.api_key = api_key
        self.access_token = access_token
        self.on_tick_callback = on_tick_callback

        self.reconnect_count: int = 0
        self.last_tick_time: float = 0.0
        self.subscribed_instruments: Set[int] = set()
        self._backoff: float = 1.0
        self._kws = None
        self._connected: bool = False

    def connect(self, instruments: List[int]) -> None:
        """Subscribe to instrument tokens and start the WebSocket."""
        try:
            from kiteconnect import KiteTicker
        except ImportError:
            logger.error("kiteconnect package not installed; cannot start WebSocket feed")
            return

        self.subscribed_instruments = set(instruments)
        self._kws = KiteTicker(self.api_key, self.access_token)

        self._kws.on_ticks = self._on_ticks
        self._kws.on_connect = self._on_connect
        self._kws.on_close = self._on_close
        self._kws.on_error = self._on_error

        logger.info("Connecting WebSocket feed for %d instruments", len(instruments))
        self._kws.connect(threaded=True)

    def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._kws:
            try:
                self._kws.close()
            except Exception:
                pass
        self._connected = False
        logger.info("WebSocket feed disconnected")

    # ---- KiteTicker callbacks ----

    def _on_connect(self, ws, response) -> None:
        """Called when WebSocket connects; subscribe to instruments."""
        self._connected = True
        self._backoff = 1.0
        tokens = list(self.subscribed_instruments)
        if tokens:
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
        logger.info("WebSocket connected, subscribed to %d instruments", len(tokens))

    def _on_ticks(self, ws, ticks: List[Dict]) -> None:
        """Called on each tick batch."""
        self.last_tick_time = time.time()
        try:
            self.on_tick_callback(ticks)
        except Exception:
            logger.exception("Error in tick callback")

    def _on_close(self, ws, code, reason) -> None:
        """Called when WebSocket closes; attempt reconnect with backoff."""
        self._connected = False
        self.reconnect_count += 1
        logger.warning(
            "WebSocket closed (code=%s, reason=%s). Reconnect #%d in %.1fs",
            code, reason, self.reconnect_count, self._backoff,
        )
        time.sleep(self._backoff)
        self._backoff = min(self._backoff * 2, self.MAX_BACKOFF)

    def _on_error(self, ws, code, reason) -> None:
        """Called on WebSocket error."""
        logger.error("WebSocket error: code=%s reason=%s", code, reason)

    # ---- Health ----

    def is_healthy(self) -> bool:
        """True if we received a tick within the last HEALTH_TIMEOUT seconds."""
        if self.last_tick_time == 0.0:
            return self._connected
        return (time.time() - self.last_tick_time) < self.HEALTH_TIMEOUT

    def get_stats(self) -> Dict:
        """Return health metrics."""
        now = time.time()
        return {
            "connected": self._connected,
            "reconnect_count": self.reconnect_count,
            "last_tick_age_s": round(now - self.last_tick_time, 1) if self.last_tick_time else None,
            "subscribed_instruments": len(self.subscribed_instruments),
            "healthy": self.is_healthy(),
        }
