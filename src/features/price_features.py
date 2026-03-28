"""Price and trend features."""

import numpy as np
import pandas as pd


def returns(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    """Multi-horizon returns.

    Args:
        df: OHLCV DataFrame.
        periods: List of lookback periods. Default [1, 5, 10, 20].

    Returns:
        DataFrame with columns like returns_1, returns_5, etc.
    """
    if periods is None:
        periods = [1, 5, 10, 20]
    result = pd.DataFrame(index=df.index)
    for p in periods:
        result[f"returns_{p}"] = df["close"].pct_change(p)
    return result


def ema(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    """Exponential moving averages.

    Args:
        df: OHLCV DataFrame.
        periods: List of EMA periods. Default [9, 21, 50].

    Returns:
        DataFrame with columns like ema_9, ema_21, etc.
    """
    if periods is None:
        periods = [9, 21, 50]
    result = pd.DataFrame(index=df.index)
    for p in periods:
        result[f"ema_{p}"] = df["close"].ewm(span=p, adjust=False).mean()
    return result


def sma(df: pd.DataFrame, periods: list = None) -> pd.DataFrame:
    """Simple moving averages.

    Args:
        df: OHLCV DataFrame.
        periods: List of SMA periods. Default [10, 20, 50].

    Returns:
        DataFrame with columns like sma_10, sma_20, etc.
    """
    if periods is None:
        periods = [10, 20, 50]
    result = pd.DataFrame(index=df.index)
    for p in periods:
        result[f"sma_{p}"] = df["close"].rolling(window=p).mean()
    return result


def ema_sma_gap(df: pd.DataFrame) -> pd.DataFrame:
    """EMA-SMA crossover distance for common periods.

    Returns:
        DataFrame with columns ema_sma_gap_10, ema_sma_gap_20, ema_sma_gap_50.
    """
    result = pd.DataFrame(index=df.index)
    for p in [10, 20, 50]:
        ema_val = df["close"].ewm(span=p, adjust=False).mean()
        sma_val = df["close"].rolling(window=p).mean()
        result[f"ema_sma_gap_{p}"] = (ema_val - sma_val) / sma_val * 100
    return result


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average Directional Index.

    Uses the standard Wilder smoothing method.

    Args:
        df: OHLCV DataFrame.
        period: ADX period. Default 14.

    Returns:
        pd.Series of ADX values.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Wilder smoothing
    atr_val = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_val
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean() / atr_val

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx_val = dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    adx_val.name = "adx"
    return adx_val


def vwap(df: pd.DataFrame) -> pd.Series:
    """Volume Weighted Average Price (cumulative).

    For daily bars this computes cumulative VWAP over the entire series.

    Args:
        df: OHLCV DataFrame.

    Returns:
        pd.Series of VWAP values.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    vwap_val = cum_tp_vol / cum_vol.replace(0, np.nan)
    vwap_val.name = "vwap"
    return vwap_val


def donchian(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Donchian channel breakout distance.

    Returns:
        DataFrame with donchian_upper, donchian_lower, donchian_mid,
        donchian_position (0-1 position within channel).
    """
    result = pd.DataFrame(index=df.index)
    result["donchian_upper"] = df["high"].rolling(window=period).max()
    result["donchian_lower"] = df["low"].rolling(window=period).min()
    result["donchian_mid"] = (result["donchian_upper"] + result["donchian_lower"]) / 2
    channel_width = result["donchian_upper"] - result["donchian_lower"]
    result["donchian_position"] = (df["close"] - result["donchian_lower"]) / channel_width.replace(0, np.nan)
    return result


def trend_slope(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Rolling linear regression slope of close prices.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window size. Default 20.

    Returns:
        pd.Series of slope values (normalized by price).
    """
    close = df["close"]
    x = np.arange(period, dtype=float)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    slopes = pd.Series(np.nan, index=df.index)
    close_vals = close.values

    for i in range(period - 1, len(close_vals)):
        y = close_vals[i - period + 1: i + 1]
        if np.any(np.isnan(y)):
            continue
        y_mean = y.mean()
        slope = ((x - x_mean) * (y - y_mean)).sum() / x_var
        # Normalize by price level
        slopes.iloc[i] = slope / y_mean * 100

    slopes.name = "trend_slope"
    return slopes
