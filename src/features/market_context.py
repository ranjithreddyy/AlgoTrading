"""Cross-market context features.

Functions for computing market-level and cross-market signals from OHLCV data.
"""

import numpy as np
import pandas as pd


def nifty_return(nifty_df, periods=None):
    """Compute NIFTY returns at various horizons.

    Args:
        nifty_df: DataFrame with 'close' column for NIFTY.
        periods: List of periods (in bars) for return computation.
                 Defaults to [1, 5].

    Returns:
        pd.DataFrame with columns like 'nifty_return_1', 'nifty_return_5'.
    """
    if periods is None:
        periods = [1, 5]

    result = pd.DataFrame(index=nifty_df.index)
    for p in periods:
        result[f"nifty_return_{p}"] = nifty_df["close"].pct_change(p)
    return result


def market_breadth(stock_dfs, period=20):
    """Compute market breadth as percentage of stocks above their SMA.

    Args:
        stock_dfs: Dict of symbol -> DataFrame, each with 'close' column.
        period: SMA period (default 20).

    Returns:
        pd.Series of breadth values (0 to 1) aligned to the common index.
    """
    above_sma = {}
    for symbol, df in stock_dfs.items():
        sma = df["close"].rolling(period).mean()
        above_sma[symbol] = (df["close"] > sma).astype(float)

    breadth_df = pd.DataFrame(above_sma)
    return breadth_df.mean(axis=1).rename("market_breadth")


def opening_gap(df):
    """Compute opening gap as (open - prev_close) / prev_close.

    Args:
        df: DataFrame with 'open' and 'close' columns.

    Returns:
        pd.Series of opening gap percentages.
    """
    prev_close = df["close"].shift(1)
    return ((df["open"] - prev_close) / prev_close).rename("opening_gap")


def time_of_day_bucket(df):
    """Categorize timestamps into intraday time buckets.

    Buckets:
        - open: 09:15 - 09:45
        - morning: 09:45 - 11:30
        - midday: 11:30 - 13:30
        - afternoon: 13:30 - 14:45
        - close: 14:45 - 15:30

    Args:
        df: DataFrame with a datetime index or 'date' column containing
            intraday timestamps.

    Returns:
        pd.Series of bucket labels.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        times = df.index
    elif "date" in df.columns:
        times = pd.to_datetime(df["date"])
    else:
        return pd.Series("unknown", index=df.index, name="time_bucket")

    hours_minutes = times.hour * 60 + times.minute

    conditions = [
        hours_minutes < 9 * 60 + 45,   # open: before 09:45
        hours_minutes < 11 * 60 + 30,   # morning: 09:45 - 11:30
        hours_minutes < 13 * 60 + 30,   # midday: 11:30 - 13:30
        hours_minutes < 14 * 60 + 45,   # afternoon: 13:30 - 14:45
    ]
    choices = ["open", "morning", "midday", "afternoon"]

    buckets = np.select(conditions, choices, default="close")
    return pd.Series(buckets, index=df.index, name="time_bucket")


def gap_classification(df):
    """Classify opening gap as small, medium, or large.

    Thresholds:
        - small: abs(gap) < 0.5%
        - medium: 0.5% <= abs(gap) < 1.5%
        - large: abs(gap) >= 1.5%

    Args:
        df: DataFrame with 'open' and 'close' columns.

    Returns:
        pd.Series of gap classifications.
    """
    gap = opening_gap(df).abs()

    conditions = [
        gap < 0.005,
        gap < 0.015,
    ]
    choices = ["small", "medium"]

    labels = np.select(conditions, choices, default="large")
    return pd.Series(labels, index=df.index, name="gap_classification")
