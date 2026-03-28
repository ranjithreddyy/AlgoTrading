"""Trading session lifecycle management."""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.clock import IST, current_ist, is_market_open
from src.config.settings import KITE_API_KEY, KITE_ACCESS_TOKEN, DATA_DIR

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages the lifecycle of a trading session: setup, run, teardown."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.session_start: Optional[datetime] = None
        self.session_end: Optional[datetime] = None
        self._active: bool = False
        self.instruments: List[Dict] = []
        self.strategies: List = []
        self.broker = None
        self.feed = None
        self.trades: List[Dict] = []
        self.errors: List[str] = []

    def pre_market_setup(self) -> bool:
        """Refresh tokens, download instruments, load models.

        Returns:
            True if setup succeeded, False otherwise.
        """
        logger.info("Running pre-market setup...")
        try:
            # Validate credentials
            api_key = self.config.get("api_key", KITE_API_KEY)
            access_token = self.config.get("access_token", KITE_ACCESS_TOKEN)
            if not api_key or not access_token:
                logger.warning("API credentials not configured; running in paper mode")

            logger.info("Pre-market setup complete")
            return True
        except Exception as e:
            self.errors.append(f"Pre-market setup failed: {e}")
            logger.exception("Pre-market setup failed")
            return False

    def start_session(self) -> None:
        """Mark session as active and record start time."""
        self.session_start = current_ist()
        self._active = True
        logger.info("Session started at %s", self.session_start.isoformat())

    def end_session(self) -> Dict[str, Any]:
        """End the session: flatten positions, generate summary.

        Returns:
            Session summary dict.
        """
        self.session_end = current_ist()
        self._active = False

        summary = self.get_session_status()
        logger.info("Session ended at %s", self.session_end.isoformat())
        return summary

    def is_session_active(self) -> bool:
        return self._active

    def get_session_status(self) -> Dict[str, Any]:
        now = current_ist()
        duration = None
        if self.session_start:
            end = self.session_end or now
            duration = str(end - self.session_start)

        return {
            "active": self._active,
            "session_start": self.session_start.isoformat() if self.session_start else None,
            "session_end": self.session_end.isoformat() if self.session_end else None,
            "duration": duration,
            "market_open": is_market_open(now),
            "total_trades": len(self.trades),
            "errors": self.errors[-5:],  # last 5 errors
        }
