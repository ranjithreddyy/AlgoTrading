"""
CSV-based storage for market OHLCV data.
Directory layout: {data_dir}/market/{exchange}/{symbol}/{interval}/*.csv
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd


class DataStorage:
    """Read and write OHLCV bar data as CSV files."""

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Base data directory (e.g. 'data').
        """
        self.data_dir = Path(data_dir)

    def _symbol_dir(self, symbol: str, exchange: str, interval: str) -> Path:
        return self.data_dir / "market" / exchange / symbol / interval

    def save_bars(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        bars_df: pd.DataFrame,
    ) -> Path:
        """Save bars DataFrame to CSV, merging with any existing data.

        Args:
            symbol: Trading symbol (e.g. RELIANCE).
            exchange: Exchange name (e.g. NSE, INDEX).
            interval: Candle interval (e.g. day, 15minute).
            bars_df: DataFrame with columns: date, open, high, low, close, volume.

        Returns:
            Path to the written CSV file.
        """
        out_dir = self._symbol_dir(symbol, exchange, interval)
        out_dir.mkdir(parents=True, exist_ok=True)

        csv_path = out_dir / "data.csv"

        if bars_df.empty:
            return csv_path

        df = bars_df.copy()
        # Normalise the date column
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

        # Merge with existing data if present
        if csv_path.exists():
            existing = pd.read_csv(csv_path, parse_dates=["date"])
            df = pd.concat([existing, df], ignore_index=True)

        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
        df.to_csv(csv_path, index=False)
        return csv_path

    def load_bars(
        self,
        symbol: str,
        exchange: str,
        interval: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """Load bars from CSV with optional date filtering.

        Args:
            symbol: Trading symbol.
            exchange: Exchange name.
            interval: Candle interval.
            from_date: Optional start date string (YYYY-MM-DD).
            to_date: Optional end date string (YYYY-MM-DD).

        Returns:
            DataFrame of bars. Empty DataFrame if no data found.
        """
        sym_dir = self._symbol_dir(symbol, exchange, interval)

        # Collect all CSVs in the interval directory
        csv_files = sorted(sym_dir.glob("*.csv")) if sym_dir.exists() else []
        if not csv_files:
            return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

        frames = [pd.read_csv(f, parse_dates=["date"]) for f in csv_files]
        df = pd.concat(frames, ignore_index=True)
        df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)

        if from_date:
            df = df[df["date"] >= pd.to_datetime(from_date)]
        if to_date:
            df = df[df["date"] <= pd.to_datetime(to_date)]

        return df.reset_index(drop=True)

    def list_symbols(self, exchange: str) -> List[str]:
        """List available symbols for a given exchange."""
        exchange_dir = self.data_dir / "market" / exchange
        if not exchange_dir.exists():
            return []
        return sorted(
            d.name for d in exchange_dir.iterdir() if d.is_dir()
        )

    def list_intervals(self, symbol: str, exchange: str) -> List[str]:
        """List available intervals for a symbol."""
        sym_dir = self.data_dir / "market" / exchange / symbol
        if not sym_dir.exists():
            return []
        return sorted(
            d.name for d in sym_dir.iterdir() if d.is_dir()
        )

    def has_data(self, symbol: str, exchange: str, interval: str) -> bool:
        """Check if any data exists for the given symbol/exchange/interval."""
        sym_dir = self._symbol_dir(symbol, exchange, interval)
        if not sym_dir.exists():
            return False
        return any(sym_dir.glob("*.csv"))

    def get_date_range(
        self, symbol: str, exchange: str, interval: str
    ) -> Optional[Tuple[datetime, datetime]]:
        """Return (earliest_date, latest_date) or None if no data."""
        df = self.load_bars(symbol, exchange, interval)
        if df.empty:
            return None
        return (df["date"].min().to_pydatetime(), df["date"].max().to_pydatetime())
