"""Mean reversion features."""

import numpy as np
import pandas as pd


def rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Relative Strength Index.

    Uses Wilder's smoothing method (exponential moving average).

    Args:
        df: OHLCV DataFrame.
        period: RSI period. Default 14.

    Returns:
        pd.Series of RSI values (0-100).
    """
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_val = 100 - 100 / (1 + rs)
    rsi_val.name = "rsi"
    return rsi_val


def _streak(series: pd.Series) -> pd.Series:
    """Count consecutive up/down streak length."""
    diff = series.diff()
    sign = np.sign(diff)
    streaks = pd.Series(0.0, index=series.index)
    for i in range(1, len(sign)):
        if sign.iloc[i] == sign.iloc[i - 1] and sign.iloc[i] != 0:
            streaks.iloc[i] = streaks.iloc[i - 1] + sign.iloc[i]
        elif sign.iloc[i] != 0:
            streaks.iloc[i] = sign.iloc[i]
    return streaks


def connors_rsi(df: pd.DataFrame) -> pd.Series:
    """Connors RSI - 3-component RSI.

    Components:
    1. RSI(close, 3)
    2. RSI(streak, 2)
    3. Percent rank of 1-day return over 100 bars

    Args:
        df: OHLCV DataFrame.

    Returns:
        pd.Series of Connors RSI values (0-100).
    """
    # Component 1: short RSI
    rsi_3 = rsi(df, period=3)

    # Component 2: streak RSI
    streak = _streak(df["close"])
    streak_df = pd.DataFrame({"close": streak}, index=df.index)
    # Use a simple RSI on the streak
    delta = streak.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=0.5, min_periods=2, adjust=False).mean()
    avg_loss = loss.ewm(alpha=0.5, min_periods=2, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi_streak = 100 - 100 / (1 + rs)

    # Component 3: percent rank of 1-day return
    ret_1 = df["close"].pct_change(1)
    pct_rank = ret_1.rolling(window=100).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    ) * 100

    crsi = (rsi_3 + rsi_streak + pct_rank) / 3
    crsi.name = "connors_rsi"
    return crsi


def bollinger_zscore(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Price z-score relative to Bollinger Band.

    (close - SMA) / rolling_std

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of z-score values.
    """
    sma = df["close"].rolling(window=period).mean()
    rolling_std = df["close"].rolling(window=period).std()
    z = (df["close"] - sma) / rolling_std.replace(0, np.nan)
    z.name = "bollinger_zscore"
    return z


def vwap_deviation(df: pd.DataFrame) -> pd.Series:
    """(close - VWAP) / VWAP as percentage.

    Args:
        df: OHLCV DataFrame.

    Returns:
        pd.Series of VWAP deviation percentages.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_vol = df["volume"].cumsum()
    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    vwap_val = cum_tp_vol / cum_vol.replace(0, np.nan)

    dev = (df["close"] - vwap_val) / vwap_val * 100
    dev.name = "vwap_deviation"
    return dev


def reversal_score(df: pd.DataFrame, period: int = 5) -> pd.Series:
    """Short-horizon reversal signal.

    Negative of the short-term return (mean reversion assumes reversal).

    Args:
        df: OHLCV DataFrame.
        period: Lookback period. Default 5.

    Returns:
        pd.Series of reversal score values.
    """
    ret = df["close"].pct_change(period)
    score = -ret
    score.name = "reversal_score"
    return score
