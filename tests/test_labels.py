"""Tests for labeling modules."""

import numpy as np
import pandas as pd
import pytest

from src.labels.horizon_returns import binary_label, forward_returns
from src.labels.meta_labels import meta_label
from src.labels.triple_barrier import triple_barrier_label


@pytest.fixture
def price_df():
    """50-bar synthetic price DataFrame."""
    np.random.seed(77)
    n = 50
    dates = pd.date_range("2025-06-01", periods=n, freq="B")
    base = 200.0
    closes = base + np.cumsum(np.random.randn(n) * 2)
    return pd.DataFrame({
        "date": dates,
        "open": closes + np.random.randn(n) * 0.5,
        "high": closes + np.abs(np.random.randn(n) * 1.5),
        "low": closes - np.abs(np.random.randn(n) * 1.5),
        "close": closes.round(2),
        "volume": np.random.randint(100_000, 500_000, size=n),
    })


# ── Forward returns ──────────────────────────────────────────────
def test_forward_returns_length(price_df):
    """Output length must match input length."""
    result = forward_returns(price_df, horizons=[1, 5])
    assert len(result) == len(price_df), "Length mismatch"


# ── Triple barrier ───────────────────────────────────────────────
def test_triple_barrier_values(price_df):
    """Triple barrier labels should only contain -1, 0, or +1."""
    labels = triple_barrier_label(price_df, take_profit=0.03, stop_loss=0.02, max_holding=10)
    unique = set(labels.unique())
    assert unique.issubset({-1, 0, 1}), f"Unexpected label values: {unique}"


# ── Binary label ─────────────────────────────────────────────────
def test_binary_label_values(price_df):
    """Binary labels should only contain 0 or 1."""
    rets = price_df["close"].pct_change(1).dropna()
    labels = binary_label(rets)
    unique = set(labels.unique())
    assert unique.issubset({0, 1}), f"Unexpected label values: {unique}"


# ── Meta labels ──────────────────────────────────────────────────
def test_meta_label_alignment(price_df):
    """Meta labels should align with the signal length."""
    n = len(price_df)
    # Create a primary signal: +1 / -1 / 0
    np.random.seed(99)
    signal = pd.Series(
        np.random.choice([-1, 0, 1], size=n, p=[0.3, 0.4, 0.3]),
        index=price_df.index,
    )
    returns = price_df["close"].pct_change(1)

    meta = meta_label(signal, returns)
    assert len(meta) == n, "Meta label length must match input"

    # Where signal is 0, meta should be NaN
    zero_mask = signal == 0
    assert meta[zero_mask].isna().all(), "Meta should be NaN where signal is 0"

    # Where signal is non-zero, meta should be 0 or 1
    nonzero_mask = signal != 0
    valid = meta[nonzero_mask].dropna()
    if len(valid) > 0:
        unique = set(valid.unique())
        assert unique.issubset({0, 1}), f"Meta label values must be 0 or 1, got {unique}"
