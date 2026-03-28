"""
Ingestion pipeline: fetch -> validate -> store historical OHLCV data.
"""

from datetime import datetime
from typing import List, Optional, Dict

import pandas as pd

from src.data.historical_loader import HistoricalLoader
from src.data.storage import DataStorage
from src.data.quality import validate_bars, fix_bars


class IngestPipeline:
    """Orchestrates fetching, validating, and storing historical bar data."""

    def __init__(self, kite, storage: DataStorage, loader: HistoricalLoader):
        """
        Args:
            kite: Authenticated KiteConnect instance (used for instrument lookups).
            storage: DataStorage instance for reading/writing CSVs.
            loader: HistoricalLoader instance for API calls.
        """
        self.kite = kite
        self.storage = storage
        self.loader = loader
        self._token_cache: Dict[str, int] = {}

    def _resolve_token(self, symbol: str, exchange: str) -> Optional[int]:
        """Resolve a trading symbol to its instrument token."""
        cache_key = f"{exchange}:{symbol}"
        if cache_key in self._token_cache:
            return self._token_cache[cache_key]

        try:
            instruments = self.kite.instruments(exchange)
            for inst in instruments:
                key = f"{exchange}:{inst['tradingsymbol']}"
                self._token_cache[key] = inst["instrument_token"]

            return self._token_cache.get(cache_key)
        except Exception as e:
            print(f"  ERROR resolving token for {symbol} on {exchange}: {e}")
            return None

    def ingest_stock(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: datetime,
        to_date: datetime,
    ) -> Dict:
        """Full ingestion pipeline for a single symbol/interval.

        Fetch -> validate -> fix -> store.

        Returns:
            Summary dict with keys: symbol, exchange, interval, bars, issues, path.
        """
        result = {
            "symbol": symbol,
            "exchange": exchange,
            "interval": interval,
            "bars": 0,
            "issues": [],
            "path": None,
        }

        # Resolve token
        token = self._resolve_token(symbol, exchange)
        if token is None:
            result["issues"].append(f"Could not resolve instrument token for {symbol}")
            return result

        print(f"  Fetching {symbol} ({exchange}) {interval} "
              f"from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}...")

        # Fetch
        bars = self.loader.fetch_chunked(token, from_date, to_date, interval)
        if not bars:
            result["issues"].append("No data returned from API")
            return result

        df = pd.DataFrame(bars)

        # Validate
        is_valid, issues = validate_bars(df)
        result["issues"] = issues
        if issues:
            print(f"  Quality issues: {issues}")

        # Fix
        df = fix_bars(df)
        result["bars"] = len(df)

        # Store
        path = self.storage.save_bars(symbol, exchange, interval, df)
        result["path"] = str(path)
        print(f"  Saved {len(df)} bars to {path}")

        return result

    def ingest_batch(
        self,
        symbols: List[str],
        exchange: str,
        intervals: List[str],
        from_date: datetime,
        to_date: datetime,
    ) -> List[Dict]:
        """Batch ingest multiple symbols and intervals.

        Args:
            symbols: List of trading symbols.
            exchange: Exchange name.
            intervals: List of candle intervals.
            from_date: Start date.
            to_date: End date.

        Returns:
            List of summary dicts (one per symbol/interval combination).
        """
        results = []
        total = len(symbols) * len(intervals)
        count = 0

        for symbol in symbols:
            for interval in intervals:
                count += 1
                print(f"\n[{count}/{total}] {symbol} | {interval}")
                r = self.ingest_stock(symbol, exchange, interval, from_date, to_date)
                results.append(r)

        return results

    def backfill(self, symbol: str, exchange: str, interval: str) -> Dict:
        """Detect the end of existing data and fetch newer bars to fill the gap.

        Args:
            symbol: Trading symbol.
            exchange: Exchange name.
            interval: Candle interval.

        Returns:
            Summary dict from ingest_stock for the backfilled range.
        """
        date_range = self.storage.get_date_range(symbol, exchange, interval)
        if date_range is None:
            # No existing data -- nothing to backfill from
            return {
                "symbol": symbol,
                "exchange": exchange,
                "interval": interval,
                "bars": 0,
                "issues": ["No existing data to backfill from"],
                "path": None,
            }

        _, latest = date_range
        to_date = datetime.now()
        if latest.date() >= to_date.date():
            print(f"  {symbol} {interval}: already up to date")
            return {
                "symbol": symbol,
                "exchange": exchange,
                "interval": interval,
                "bars": 0,
                "issues": [],
                "path": None,
            }

        print(f"  Backfilling {symbol} {interval} from {latest.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
        return self.ingest_stock(symbol, exchange, interval, latest, to_date)
