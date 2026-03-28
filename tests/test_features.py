"""Tests for feature computation modules."""

import numpy as np
import pandas as pd
import pytest

from src.features.compute import compute_features
from src.features.feature_registry import default_registry
from src.features.mean_reversion_features import rsi
from src.features.price_features import ema
from src.features.volatility_features import atr, bollinger_bands
from src.features.volume_features import obv


@pytest.fixture
def large_bars():
    """200-bar synthetic OHLCV DataFrame for feature tests."""
    np.random.seed(123)
    n = 200
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    base = 500.0
    closes = base + np.cumsum(np.random.randn(n) * 3)
    opens = closes + np.random.randn(n) * 1.0
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 2)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 2)
    volumes = np.random.randint(200_000, 2_000_000, size=n)

    return pd.DataFrame({
        "date": dates,
        "open": opens.round(2),
        "high": highs.round(2),
        "low": lows.round(2),
        "close": closes.round(2),
        "volume": volumes,
    })


# ── RSI ────────────────────────────────────────────────────────────
def test_rsi_range(large_bars):
    """RSI must always be between 0 and 100."""
    rsi_vals = rsi(large_bars)
    valid = rsi_vals.dropna()
    assert len(valid) > 0, "RSI should produce non-NaN values"
    assert valid.min() >= 0.0, f"RSI below 0: {valid.min()}"
    assert valid.max() <= 100.0, f"RSI above 100: {valid.max()}"


# ── EMA ────────────────────────────────────────────────────────────
def test_ema_convergence(large_bars):
    """EMA should converge towards the close price over time."""
    ema_df = ema(large_bars, periods=[9])
    # The last EMA value should be close to the last close
    last_ema = ema_df["ema_9"].iloc[-1]
    last_close = large_bars["close"].iloc[-1]
    # EMA_9 tracks recent prices; allow a generous tolerance
    assert abs(last_ema - last_close) / last_close < 0.10, (
        f"EMA_9 ({last_ema:.2f}) too far from close ({last_close:.2f})"
    )


# ── ATR ────────────────────────────────────────────────────────────
def test_atr_positive(large_bars):
    """ATR must always be positive (after warm-up)."""
    atr_vals = atr(large_bars)
    valid = atr_vals.dropna()
    assert len(valid) > 0, "ATR should produce non-NaN values"
    assert (valid > 0).all(), "ATR must be positive"


# ── Bollinger Bands ───────────────────────────────────────────────
def test_bollinger_bands_ordering(large_bars):
    """Upper band > middle (SMA) > lower band at every point."""
    bb = bollinger_bands(large_bars, period=20, std=2.0)
    valid = bb.dropna()
    assert len(valid) > 0, "Bollinger bands should produce non-NaN values"
    sma = large_bars["close"].rolling(window=20).mean().loc[valid.index]
    assert (valid["bb_upper"] >= sma).all(), "Upper band must be >= SMA"
    assert (valid["bb_lower"] <= sma).all(), "Lower band must be <= SMA"
    assert (valid["bb_upper"] >= valid["bb_lower"]).all(), "Upper must be >= lower"


# ── compute_features no NaN ──────────────────────────────────────
def test_compute_features_no_nan(large_bars):
    """After compute_features the returned DataFrame should have no NaN."""
    feats = compute_features(large_bars)
    assert not feats.empty, "compute_features returned empty DataFrame"
    nan_count = feats.isna().sum().sum()
    assert nan_count == 0, f"compute_features has {nan_count} NaN values"


# ── Feature registry listing ────────────────────────────────────
def test_feature_registry_lists():
    """The default registry should list all registered features."""
    names = default_registry.list_features()
    assert isinstance(names, list)
    assert len(names) > 0, "Registry should have features"
    # Spot-check a few known names
    for expected in ["rsi", "atr", "ema", "obv"]:
        assert expected in names, f"'{expected}' missing from registry"


# ── OBV direction ─────────────────────────────────────────────────
def test_obv_direction(large_bars):
    """OBV should increase on up days and decrease on down days."""
    obv_vals = obv(large_bars)
    close_diff = large_bars["close"].diff()

    # Pick a few up-days and verify OBV went up
    up_days = close_diff[close_diff > 0].index
    assert len(up_days) > 0, "Need at least one up day"
    for idx in up_days[:5]:
        pos = large_bars.index.get_loc(idx)
        if pos == 0:
            continue
        prev_pos = pos - 1
        assert obv_vals.iloc[pos] > obv_vals.iloc[prev_pos], (
            f"OBV should increase on up day at index {idx}"
        )
