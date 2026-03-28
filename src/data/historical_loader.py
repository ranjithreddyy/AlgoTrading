"""
Historical data loader with rate limiting and chunked fetching.
Wraps the KiteConnect historical_data API.
"""

import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional


# Chunk size limits imposed by Kite API (max days per request)
INTERVAL_CHUNK_DAYS = {
    "minute": 60,
    "3minute": 60,
    "5minute": 100,
    "10minute": 100,
    "15minute": 200,
    "30minute": 200,
    "60minute": 200,
    "day": 2000,
}

RATE_LIMIT_DELAY = 0.35  # seconds between API calls (~3 req/sec)


class HistoricalLoader:
    """Fetches historical OHLCV bars from Kite API with rate limiting."""

    def __init__(self, kite):
        """
        Args:
            kite: An authenticated KiteConnect instance.
        """
        self.kite = kite
        self._last_call_time = 0.0

    def _rate_limit(self):
        """Enforce minimum delay between API calls."""
        elapsed = time.time() - self._last_call_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self._last_call_time = time.time()

    def fetch(
        self,
        token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "day",
    ) -> List[Dict]:
        """Fetch historical bars for a single date range (no chunking).

        Args:
            token: Instrument token.
            from_date: Start date.
            to_date: End date.
            interval: Candle interval (minute, 5minute, 15minute, day, etc.)

        Returns:
            List of bar dicts with keys: date, open, high, low, close, volume.
        """
        self._rate_limit()
        data = self.kite.historical_data(token, from_date, to_date, interval)
        return data

    def fetch_chunked(
        self,
        token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str = "day",
    ) -> List[Dict]:
        """Fetch historical bars, automatically chunking by interval limits.

        Splits the date range into chunks that respect Kite API limits
        and concatenates the results.

        Args:
            token: Instrument token.
            from_date: Start date.
            to_date: End date.
            interval: Candle interval.

        Returns:
            List of bar dicts covering the full date range.
        """
        chunk_days = INTERVAL_CHUNK_DAYS.get(interval, 60)
        all_bars: List[Dict] = []

        current = from_date
        while current < to_date:
            chunk_end = min(current + timedelta(days=chunk_days), to_date)
            try:
                bars = self.fetch(token, current, chunk_end, interval)
                all_bars.extend(bars)
            except Exception as e:
                print(f"  ERROR fetching token={token} interval={interval} "
                      f"{current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')}: {e}")
            current = chunk_end + timedelta(days=1)

        return all_bars
