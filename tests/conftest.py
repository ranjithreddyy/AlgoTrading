"""Shared fixtures for the test suite."""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure repo root is on sys.path so 'src.*' imports work.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.data.storage import DataStorage


@pytest.fixture
def sample_df():
    """Load RELIANCE daily OHLCV data from disk."""
    storage = DataStorage(str(REPO_ROOT / "data"))
    df = storage.load_bars("RELIANCE", "NSE", "day")
    assert not df.empty, "RELIANCE day data must exist for tests"
    return df


@pytest.fixture
def sample_bars():
    """Small synthetic 20-bar OHLCV DataFrame for fast tests."""
    import numpy as np

    np.random.seed(42)
    n = 20
    dates = pd.date_range("2026-01-05", periods=n, freq="B")
    base = 100.0
    closes = base + np.cumsum(np.random.randn(n) * 2)
    opens = closes + np.random.randn(n) * 0.5
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n))
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n))
    volumes = np.random.randint(100_000, 1_000_000, size=n)

    df = pd.DataFrame({
        "date": dates,
        "open": opens.round(2),
        "high": highs.round(2),
        "low": lows.round(2),
        "close": closes.round(2),
        "volume": volumes,
    })
    return df
