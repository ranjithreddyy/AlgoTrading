"""Tests for data modules: DataStorage, quality validation."""

from pathlib import Path

import pandas as pd
import pytest

from src.data.storage import DataStorage
from src.data.quality import validate_bars, fix_bars

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def storage():
    return DataStorage(str(REPO_ROOT / "data"))


# ── DataStorage ──────────────────────────────────────────────────────────────

def test_storage_load(storage):
    """Load RELIANCE day data and verify it has expected columns."""
    df = storage.load_bars("RELIANCE", "NSE", "day")
    assert not df.empty
    for col in ["date", "open", "high", "low", "close", "volume"]:
        assert col in df.columns
    assert len(df) >= 5  # we know there are ~20 rows


def test_storage_has_data(storage):
    """has_data returns True for RELIANCE day data."""
    assert storage.has_data("RELIANCE", "NSE", "day") is True
    assert storage.has_data("NONEXISTENT_SYMBOL", "NSE", "day") is False


def test_storage_list_symbols(storage):
    """list_symbols for NSE returns a non-empty list containing RELIANCE."""
    symbols = storage.list_symbols("NSE")
    assert isinstance(symbols, list)
    assert len(symbols) > 0
    assert "RELIANCE" in symbols


def test_storage_date_range(storage):
    """get_date_range returns a valid (min, max) tuple for RELIANCE."""
    result = storage.get_date_range("RELIANCE", "NSE", "day")
    assert result is not None
    start, end = result
    assert start <= end


# ── Data Quality ─────────────────────────────────────────────────────────────

def test_quality_valid_data(sample_bars):
    """Clean synthetic data should pass validation."""
    is_valid, issues = validate_bars(sample_bars)
    assert is_valid is True
    assert issues == []


def test_quality_invalid_data():
    """Detect bars where high < low."""
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-05", periods=3, freq="B"),
        "open": [100.0, 200.0, 300.0],
        "high": [90.0, 210.0, 310.0],   # first row: high < low
        "low": [95.0, 195.0, 295.0],
        "close": [92.0, 205.0, 305.0],
        "volume": [1000, 2000, 3000],
    })
    is_valid, issues = validate_bars(df)
    assert is_valid is False
    assert any("high < low" in issue for issue in issues)


def test_quality_fix():
    """fix_bars removes invalid rows (high < low)."""
    df = pd.DataFrame({
        "date": pd.date_range("2026-01-05", periods=4, freq="B"),
        "open": [100.0, 200.0, 300.0, 400.0],
        "high": [90.0, 210.0, 310.0, 410.0],   # row 0: high < low
        "low": [95.0, 195.0, 295.0, 395.0],
        "close": [92.0, 205.0, 305.0, 405.0],
        "volume": [1000, 2000, -500, 4000],      # row 2: negative volume
    })
    cleaned = fix_bars(df)
    # Row 0 removed (high < low), row 2 removed (negative volume)
    assert len(cleaned) == 2
    # Remaining rows should pass validation
    is_valid, issues = validate_bars(cleaned)
    assert is_valid is True
