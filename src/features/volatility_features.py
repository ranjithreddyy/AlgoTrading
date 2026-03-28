"""Volatility features."""

import numpy as np
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range.

    Args:
        df: OHLCV DataFrame.
        period: ATR period. Default 14.

    Returns:
        pd.Series of ATR values.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr_val = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    atr_val.name = "atr"
    return atr_val


def realized_vol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Realized volatility (annualized standard deviation of returns).

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of realized vol values.
    """
    log_ret = np.log(df["close"] / df["close"].shift(1))
    rv = log_ret.rolling(window=period).std() * np.sqrt(252)
    rv.name = "realized_vol"
    return rv


def parkinson_vol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Parkinson volatility estimator using high/low range.

    More efficient than close-to-close volatility.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of Parkinson vol values (annualized).
    """
    log_hl = np.log(df["high"] / df["low"])
    factor = 1.0 / (4.0 * np.log(2))
    pv = np.sqrt(factor * (log_hl ** 2).rolling(window=period).mean() * 252)
    pv.name = "parkinson_vol"
    return pv


def garman_klass_vol(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Garman-Klass volatility estimator.

    Uses open, high, low, close for a more efficient estimate.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of Garman-Klass vol values (annualized).
    """
    log_hl = np.log(df["high"] / df["low"])
    log_co = np.log(df["close"] / df["open"])

    gk = 0.5 * log_hl ** 2 - (2 * np.log(2) - 1) * log_co ** 2
    gkv = np.sqrt(gk.rolling(window=period).mean() * 252)
    gkv.name = "garman_klass_vol"
    return gkv


def bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Bollinger Bands with z-score.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.
        std: Number of standard deviations. Default 2.

    Returns:
        DataFrame with bb_upper, bb_lower, bb_zscore columns.
    """
    sma = df["close"].rolling(window=period).mean()
    rolling_std = df["close"].rolling(window=period).std()

    result = pd.DataFrame(index=df.index)
    result["bb_upper"] = sma + std * rolling_std
    result["bb_lower"] = sma - std * rolling_std
    result["bb_zscore"] = (df["close"] - sma) / rolling_std.replace(0, np.nan)
    return result


def bar_range_score(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Bar range as a percentile of recent ATR.

    (high - low) / ATR, expressed as a rolling percentile.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of bar range scores (0-1).
    """
    bar_range = df["high"] - df["low"]
    atr_val = atr(df, period=period)
    ratio = bar_range / atr_val.replace(0, np.nan)

    score = ratio.rolling(window=period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )
    score.name = "bar_range_score"
    return score


def intraday_vol_percentile(df: pd.DataFrame, period: int = 60) -> pd.Series:
    """Current realized vol vs rolling vol percentile.

    Args:
        df: OHLCV DataFrame.
        period: Long rolling window. Default 60.

    Returns:
        pd.Series of vol percentile values (0-1).
    """
    log_ret = np.log(df["close"] / df["close"].shift(1))
    short_vol = log_ret.rolling(window=5).std()

    percentile = short_vol.rolling(window=period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )
    percentile.name = "intraday_vol_percentile"
    return percentile
