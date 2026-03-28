"""
Instrument master module for loading, caching, and querying Zerodha instrument data.
"""

import os
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data"


class InstrumentMaster:
    """Load and query Zerodha instrument master data."""

    def __init__(self):
        self.df = pd.DataFrame()

    def load_from_csv(self, path):
        """Load instrument data from a saved CSV file.

        Args:
            path: Path to the CSV file (string or Path object).

        Returns:
            self for method chaining.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Instrument file not found: {path}")

        df = pd.read_csv(path)
        # Coerce expiry to datetime if present
        if "expiry" in df.columns:
            df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")

        if self.df.empty:
            self.df = df
        else:
            self.df = pd.concat([self.df, df], ignore_index=True)

        logger.info("Loaded %d instruments from %s", len(df), path)
        return self

    def download_and_save(self, kite, exchange, date=None):
        """Download instruments from Kite API and save to CSV.

        Args:
            kite: A KiteConnect instance (or KiteClient whose .kite attribute
                  is a KiteConnect instance).
            exchange: Exchange string, e.g. 'NSE', 'NFO'.
            date: Date string 'YYYY-MM-DD' or None for today.

        Returns:
            Path to the saved CSV file.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Support both raw KiteConnect and KiteClient wrapper
        kite_conn = getattr(kite, "kite", kite)

        instruments = kite_conn.instruments(exchange=exchange)
        df = pd.DataFrame(instruments)

        inst_dir = DATA_DIR / "raw" / "instruments" / date
        inst_dir.mkdir(parents=True, exist_ok=True)
        path = inst_dir / f"{exchange}_instruments.csv"
        df.to_csv(path, index=False)

        logger.info("Saved %d %s instruments to %s", len(df), exchange, path)

        # Coerce expiry to datetime
        if "expiry" in df.columns:
            df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")

        if self.df.empty:
            self.df = df
        else:
            self.df = pd.concat([self.df, df], ignore_index=True)

        return path

    def get_token(self, symbol, exchange="NSE"):
        """Resolve a tradingsymbol to its instrument_token.

        Args:
            symbol: The trading symbol, e.g. 'RELIANCE'.
            exchange: Exchange to search in (default 'NSE').

        Returns:
            Integer instrument_token, or None if not found.
        """
        mask = (self.df["tradingsymbol"] == symbol) & (self.df["exchange"] == exchange)
        matches = self.df.loc[mask, "instrument_token"]
        if matches.empty:
            logger.warning("Token not found for %s on %s", symbol, exchange)
            return None
        return int(matches.iloc[0])

    def get_tokens(self, symbols, exchange="NSE"):
        """Batch resolve tradingsymbols to instrument_tokens.

        Args:
            symbols: List of trading symbols.
            exchange: Exchange to search in (default 'NSE').

        Returns:
            Dict mapping symbol -> instrument_token. Missing symbols are omitted.
        """
        mask = (self.df["tradingsymbol"].isin(symbols)) & (self.df["exchange"] == exchange)
        matches = self.df.loc[mask, ["tradingsymbol", "instrument_token"]]
        result = dict(zip(matches["tradingsymbol"], matches["instrument_token"].astype(int)))

        missing = set(symbols) - set(result.keys())
        if missing:
            logger.warning("Tokens not found for: %s", missing)

        return result

    def search(self, query):
        """Search instruments by partial name or tradingsymbol match (case-insensitive).

        Args:
            query: Search string.

        Returns:
            DataFrame of matching instruments.
        """
        query_upper = query.upper()
        mask = (
            self.df["tradingsymbol"].str.upper().str.contains(query_upper, na=False)
            | self.df["name"].str.upper().str.contains(query_upper, na=False)
        )
        return self.df.loc[mask].copy()

    def filter_by_exchange(self, exchange):
        """Filter instruments by exchange.

        Args:
            exchange: Exchange string, e.g. 'NSE', 'NFO'.

        Returns:
            DataFrame of instruments for the given exchange.
        """
        return self.df.loc[self.df["exchange"] == exchange].copy()
