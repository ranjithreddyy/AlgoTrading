"""
Data quality validation and cleaning for OHLCV bar data.
"""

from typing import Tuple, List

import pandas as pd


def validate_bars(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """Validate an OHLCV DataFrame for common data quality issues.

    Checks performed:
        - high >= low
        - close between low and high
        - open between low and high
        - volume >= 0
        - no duplicate timestamps
        - gap detection in minute-level bars during market hours (09:15-15:30)

    Args:
        df: DataFrame with columns date, open, high, low, close, volume.

    Returns:
        (is_valid, issues) where issues is a list of human-readable strings.
    """
    if df.empty:
        return True, []

    issues: List[str] = []

    # Ensure date column is datetime
    dates = pd.to_datetime(df["date"])

    # high >= low
    bad_hl = (df["high"] < df["low"])
    if bad_hl.any():
        issues.append(f"high < low in {bad_hl.sum()} rows")

    # close between low and high
    bad_close = (df["close"] < df["low"]) | (df["close"] > df["high"])
    if bad_close.any():
        issues.append(f"close outside [low, high] in {bad_close.sum()} rows")

    # open between low and high
    bad_open = (df["open"] < df["low"]) | (df["open"] > df["high"])
    if bad_open.any():
        issues.append(f"open outside [low, high] in {bad_open.sum()} rows")

    # volume >= 0
    bad_vol = (df["volume"] < 0)
    if bad_vol.any():
        issues.append(f"negative volume in {bad_vol.sum()} rows")

    # duplicate timestamps
    dup_count = dates.duplicated().sum()
    if dup_count > 0:
        issues.append(f"{dup_count} duplicate timestamps")

    # Gap detection for minute bars (heuristic: check if data looks intraday)
    if len(df) > 1:
        median_diff = dates.diff().dropna().median()
        # If median difference is less than 1 hour, treat as intraday
        if median_diff < pd.Timedelta(hours=1):
            _check_minute_gaps(dates, issues)

    is_valid = len(issues) == 0
    return is_valid, issues


def _check_minute_gaps(dates: pd.Series, issues: List[str]):
    """Detect gaps in minute-level bars during market hours 09:15-15:30 IST."""
    market_open = pd.Timestamp("09:15:00").time()
    market_close = pd.Timestamp("15:30:00").time()

    # Filter to market-hours bars only
    times = dates.dt.time
    market_mask = (times >= market_open) & (times <= market_close)
    market_dates = dates[market_mask].sort_values().reset_index(drop=True)

    if len(market_dates) < 2:
        return

    # Group by trading day and check for large gaps within a day
    grouped = market_dates.groupby(market_dates.dt.date)
    gap_days = 0
    for day, group in grouped:
        diffs = group.diff().dropna()
        # A gap larger than 5x the median interval suggests missing bars
        median_interval = diffs.median()
        if median_interval > pd.Timedelta(0):
            large_gaps = diffs > (median_interval * 5)
            if large_gaps.any():
                gap_days += 1

    if gap_days > 0:
        issues.append(f"possible intraday gaps detected on {gap_days} trading days")


def fix_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Clean an OHLCV DataFrame by removing invalid rows, sorting, and deduplicating.

    Operations:
        - Drop rows where high < low
        - Drop rows with negative volume
        - Sort by date
        - Remove duplicate timestamps (keep first)

    Args:
        df: Raw OHLCV DataFrame.

    Returns:
        Cleaned DataFrame.
    """
    if df.empty:
        return df.copy()

    cleaned = df.copy()
    cleaned["date"] = pd.to_datetime(cleaned["date"])

    # Remove rows where high < low
    cleaned = cleaned[cleaned["high"] >= cleaned["low"]]

    # Remove rows with negative volume
    cleaned = cleaned[cleaned["volume"] >= 0]

    # Sort and deduplicate
    cleaned = cleaned.sort_values("date").drop_duplicates(subset=["date"], keep="first")

    return cleaned.reset_index(drop=True)
