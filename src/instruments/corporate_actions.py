"""Corporate actions tracker for managing splits, bonuses, and dividends.

Tracks and adjusts for corporate actions on tracked symbols.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class CorporateActionsTracker:
    """Track and manage corporate actions for stocks.

    Stores splits, bonuses, and dividends, and provides price adjustment
    utilities for historical data.
    """

    def __init__(self):
        self._actions: Dict[str, List[dict]] = {}
        self._initialize_known_actions()

    def _initialize_known_actions(self):
        """Pre-populate with known recent corporate actions for tracked stocks."""
        # Reliance bonus 1:1 in Oct 2024
        self.add_bonus("RELIANCE", "2024-10-28", "1:1")
        # ITC demerger-related adjustment
        self.add_dividend("ITC", "2024-06-14", 7.50)
        # TCS buyback related
        self.add_dividend("TCS", "2024-03-22", 73.0)
        # HDFCBANK dividend
        self.add_dividend("HDFCBANK", "2024-05-17", 19.50)

    def _ensure_symbol(self, symbol: str):
        if symbol not in self._actions:
            self._actions[symbol] = []

    def add_split(self, symbol: str, date: str, ratio: str):
        """Record a stock split.

        Args:
            symbol: Stock symbol (e.g. 'RELIANCE').
            date: Ex-date of the split (YYYY-MM-DD).
            ratio: Split ratio as string (e.g. '1:2' means 1 old = 2 new).
        """
        self._ensure_symbol(symbol)
        self._actions[symbol].append({
            "type": "split",
            "date": date,
            "ratio": ratio,
        })
        logger.info("Recorded split for %s on %s: %s", symbol, date, ratio)

    def add_bonus(self, symbol: str, date: str, ratio: str):
        """Record a bonus issue.

        Args:
            symbol: Stock symbol.
            date: Ex-date of the bonus (YYYY-MM-DD).
            ratio: Bonus ratio as string (e.g. '1:1' means 1 bonus for 1 held).
        """
        self._ensure_symbol(symbol)
        self._actions[symbol].append({
            "type": "bonus",
            "date": date,
            "ratio": ratio,
        })
        logger.info("Recorded bonus for %s on %s: %s", symbol, date, ratio)

    def add_dividend(self, symbol: str, date: str, amount: float):
        """Record an ex-dividend event.

        Args:
            symbol: Stock symbol.
            date: Ex-dividend date (YYYY-MM-DD).
            amount: Dividend amount per share.
        """
        self._ensure_symbol(symbol)
        self._actions[symbol].append({
            "type": "dividend",
            "date": date,
            "amount": amount,
        })
        logger.info("Recorded dividend for %s on %s: %.2f", symbol, date, amount)

    def get_actions(self, symbol: str, from_date: str, to_date: str) -> List[dict]:
        """Get corporate actions for a symbol within a date range.

        Args:
            symbol: Stock symbol.
            from_date: Start date (YYYY-MM-DD), inclusive.
            to_date: End date (YYYY-MM-DD), inclusive.

        Returns:
            List of action dicts within the date range, sorted by date.
        """
        if symbol not in self._actions:
            return []

        from_dt = pd.to_datetime(from_date)
        to_dt = pd.to_datetime(to_date)

        filtered = []
        for action in self._actions[symbol]:
            action_dt = pd.to_datetime(action["date"])
            if from_dt <= action_dt <= to_dt:
                filtered.append(action)

        return sorted(filtered, key=lambda a: a["date"])

    def _parse_ratio(self, ratio_str: str) -> float:
        """Parse a ratio string like '1:2' into a multiplier.

        For splits: '1:2' means 1 share becomes 2, so price adjustment = 1/2.
        For bonus: '1:1' means 1 bonus for 1 held, so price adjustment = 1/2.
        """
        parts = ratio_str.split(":")
        old_shares = float(parts[0])
        new_shares = float(parts[1])
        return old_shares / (old_shares + new_shares)

    def adjust_prices(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """Adjust historical OHLCV data for splits and bonuses.

        Adjusts prices before the action date by the appropriate factor.
        Volume is inversely adjusted. Dividends are not adjusted for
        (they affect returns, not price levels in the same way).

        Args:
            df: DataFrame with 'date', 'open', 'high', 'low', 'close', 'volume'.
            symbol: Stock symbol.

        Returns:
            DataFrame with adjusted prices.
        """
        if symbol not in self._actions:
            return df.copy()

        result = df.copy()
        if "date" in result.columns:
            result["date"] = pd.to_datetime(result["date"])

        price_cols = ["open", "high", "low", "close"]

        for action in self._actions[symbol]:
            if action["type"] not in ("split", "bonus"):
                continue

            action_date = pd.to_datetime(action["date"])
            factor = self._parse_ratio(action["ratio"])

            if "date" in result.columns:
                mask = result["date"] < action_date
            else:
                mask = result.index < action_date

            for col in price_cols:
                if col in result.columns:
                    result.loc[mask, col] = result.loc[mask, col] * factor

            if "volume" in result.columns:
                result.loc[mask, "volume"] = (
                    result.loc[mask, "volume"] / factor
                ).astype(int)

        return result

    def is_under_action(self, symbol: str, date: str) -> bool:
        """Check if a symbol has a corporate action on a specific date.

        Args:
            symbol: Stock symbol.
            date: Date to check (YYYY-MM-DD).

        Returns:
            True if there is any action on that date.
        """
        if symbol not in self._actions:
            return False

        date_str = pd.to_datetime(date).strftime("%Y-%m-%d")
        for action in self._actions[symbol]:
            if pd.to_datetime(action["date"]).strftime("%Y-%m-%d") == date_str:
                return True
        return False

    def save(self, path: str):
        """Persist corporate actions to a JSON file.

        Args:
            path: File path to save to.
        """
        with open(path, "w") as f:
            json.dump(self._actions, f, indent=2, default=str)
        logger.info("Saved corporate actions to %s", path)

    def load(self, path: str):
        """Load corporate actions from a JSON file.

        Args:
            path: File path to load from.
        """
        with open(path, "r") as f:
            self._actions = json.load(f)
        logger.info("Loaded corporate actions from %s", path)
