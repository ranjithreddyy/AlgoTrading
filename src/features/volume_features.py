"""Volume and flow features."""

import numpy as np
import pandas as pd


def relative_volume(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Relative volume: current volume / rolling mean volume.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of relative volume values.
    """
    mean_vol = df["volume"].rolling(window=period).mean()
    rv = df["volume"] / mean_vol.replace(0, np.nan)
    rv.name = "relative_volume"
    return rv


def volume_spike(df: pd.DataFrame, threshold: float = 2.0, period: int = 20) -> pd.Series:
    """Boolean volume spike detection.

    Args:
        df: OHLCV DataFrame.
        threshold: Spike threshold as multiple of average. Default 2.0.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of boolean spike indicators (1.0 or 0.0).
    """
    rv = relative_volume(df, period)
    spike = (rv >= threshold).astype(float)
    spike.name = "volume_spike"
    return spike


def obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume.

    Cumulative volume where volume is added on up days and subtracted on
    down days.

    Args:
        df: OHLCV DataFrame.

    Returns:
        pd.Series of OBV values.
    """
    direction = np.sign(df["close"].diff())
    direction.iloc[0] = 0
    obv_val = (direction * df["volume"]).cumsum()
    obv_val.name = "obv"
    return obv_val


def cmf(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Chaikin Money Flow.

    Measures the amount of Money Flow Volume over a specific period.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 20.

    Returns:
        pd.Series of CMF values (-1 to 1).
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    volume = df["volume"]

    hl_range = high - low
    mfm = ((close - low) - (high - close)) / hl_range.replace(0, np.nan)
    mfm = mfm.fillna(0)
    mfv = mfm * volume

    cmf_val = mfv.rolling(window=period).sum() / volume.rolling(window=period).sum().replace(0, np.nan)
    cmf_val.name = "cmf"
    return cmf_val


def turnover(df: pd.DataFrame) -> pd.Series:
    """Turnover: close * volume.

    Args:
        df: OHLCV DataFrame.

    Returns:
        pd.Series of turnover values.
    """
    t = df["close"] * df["volume"]
    t.name = "turnover"
    return t


def volume_momentum(df: pd.DataFrame, period: int = 10) -> pd.Series:
    """Rate of change of volume.

    Args:
        df: OHLCV DataFrame.
        period: Lookback period. Default 10.

    Returns:
        pd.Series of volume momentum values (percentage change).
    """
    vm = df["volume"].pct_change(period)
    vm.name = "volume_momentum"
    return vm
