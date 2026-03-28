"""Regime detection features."""

import numpy as np
import pandas as pd


def hurst_exponent(df: pd.DataFrame, max_lag: int = 20) -> pd.Series:
    """Rolling Hurst exponent using rescaled range (R/S) analysis.

    H < 0.5: mean-reverting
    H = 0.5: random walk
    H > 0.5: trending

    Args:
        df: OHLCV DataFrame.
        max_lag: Maximum lag for R/S calculation. Default 20.

    Returns:
        pd.Series of Hurst exponent values.
    """
    close = df["close"].values
    log_ret = np.log(close[1:] / close[:-1])

    window = max_lag * 3  # need enough data
    hurst = pd.Series(np.nan, index=df.index)

    for i in range(window, len(close)):
        ts = log_ret[i - window: i]

        lags = range(2, max_lag + 1)
        rs_values = []
        for lag in lags:
            n_chunks = len(ts) // lag
            if n_chunks < 1:
                continue
            rs_list = []
            for j in range(n_chunks):
                chunk = ts[j * lag: (j + 1) * lag]
                mean_chunk = chunk.mean()
                deviate = np.cumsum(chunk - mean_chunk)
                r = deviate.max() - deviate.min()
                s = chunk.std(ddof=1)
                if s > 0:
                    rs_list.append(r / s)
            if rs_list:
                rs_values.append((np.log(lag), np.log(np.mean(rs_list))))

        if len(rs_values) >= 3:
            x = np.array([v[0] for v in rs_values])
            y = np.array([v[1] for v in rs_values])
            # Linear regression slope = Hurst exponent
            slope = np.polyfit(x, y, 1)[0]
            hurst.iloc[i] = np.clip(slope, 0, 1)

    hurst.name = "hurst_exponent"
    return hurst


def vol_regime(df: pd.DataFrame, period: int = 60) -> pd.Series:
    """Classify volatility regime as low/normal/high/extreme.

    Uses rolling percentile of realized vol.
    0 = low (< 25th percentile)
    1 = normal (25th-75th)
    2 = high (75th-90th)
    3 = extreme (> 90th)

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 60.

    Returns:
        pd.Series of regime labels (0, 1, 2, 3).
    """
    log_ret = np.log(df["close"] / df["close"].shift(1))
    rv = log_ret.rolling(window=10).std()

    pct = rv.rolling(window=period).apply(
        lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False
    )

    regime = pd.Series(np.nan, index=df.index)
    regime = regime.where(pct.isna(), 1)  # default normal
    regime = regime.where(pct >= 0.25, 0)  # low
    regime = regime.where(~((pct >= 0.25) & (pct < 0.75)), 1)  # normal
    regime = regime.where(~((pct >= 0.75) & (pct < 0.90)), 2)  # high
    regime = regime.where(pct < 0.90, 3)  # extreme - this overwrites where pct >= 0.90

    # Simpler approach
    regime = pd.Series(np.nan, index=df.index)
    regime[pct < 0.25] = 0
    regime[(pct >= 0.25) & (pct < 0.75)] = 1
    regime[(pct >= 0.75) & (pct < 0.90)] = 2
    regime[pct >= 0.90] = 3

    regime.name = "vol_regime"
    return regime


def trend_strength(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """ADX-based trend strength score.

    Normalized to 0-1 range.

    Args:
        df: OHLCV DataFrame.
        period: ADX period. Default 20.

    Returns:
        pd.Series of trend strength values (0-1).
    """
    from src.features.price_features import adx as compute_adx

    adx_val = compute_adx(df, period=period)
    # Normalize: ADX typically ranges 0-100, clip and scale
    ts = adx_val.clip(0, 100) / 100
    ts.name = "trend_strength"
    return ts


def mean_reversion_halflife(df: pd.DataFrame, period: int = 60) -> pd.Series:
    """Ornstein-Uhlenbeck half-life estimate.

    Fits an AR(1) model on log prices and computes the half-life of
    mean reversion: half_life = -ln(2) / ln(phi) where phi is the AR(1)
    coefficient.

    Args:
        df: OHLCV DataFrame.
        period: Rolling window. Default 60.

    Returns:
        pd.Series of half-life values (in bars). Larger = less mean-reverting.
    """
    log_price = np.log(df["close"].values)
    halflife = pd.Series(np.nan, index=df.index)

    for i in range(period, len(log_price)):
        y = log_price[i - period + 1: i + 1]
        y_lag = y[:-1]
        y_curr = y[1:]

        # OLS: y_curr = alpha + phi * y_lag + epsilon
        x = np.column_stack([np.ones(len(y_lag)), y_lag])
        try:
            beta = np.linalg.lstsq(x, y_curr, rcond=None)[0]
            phi = beta[1]
            if 0 < phi < 1:
                hl = -np.log(2) / np.log(phi)
                halflife.iloc[i] = min(hl, period * 5)  # cap at 5x period
            else:
                halflife.iloc[i] = np.nan
        except np.linalg.LinAlgError:
            halflife.iloc[i] = np.nan

    halflife.name = "mean_reversion_halflife"
    return halflife
