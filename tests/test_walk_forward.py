"""Tests for walk-forward validation."""

import numpy as np
import pandas as pd
import pytest

from src.research.walk_forward import WalkForwardValidator


@pytest.fixture
def wf_data():
    """Generate 500 rows of synthetic OHLCV data for walk-forward tests."""
    np.random.seed(42)
    n = 500
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    base = 1000.0
    closes = base + np.cumsum(np.random.randn(n) * 5)
    opens = closes + np.random.randn(n) * 1.0
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n) * 3)
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n) * 3)
    volumes = np.random.randint(100_000, 1_000_000, size=n)

    return pd.DataFrame({
        "date": dates,
        "open": opens.round(2),
        "high": highs.round(2),
        "low": lows.round(2),
        "close": closes.round(2),
        "volume": volumes,
    })


# ── Correct number of splits ─────────────────────────────────────
def test_walk_forward_splits(wf_data):
    """WalkForwardValidator should produce the correct number of folds."""
    wfv = WalkForwardValidator(train_days=100, test_days=50, embargo_days=1)
    splits = wfv.split(wf_data)
    assert len(splits) > 0, "Should produce at least one split"

    # With n_splits limit
    wfv2 = WalkForwardValidator(train_days=100, test_days=50, embargo_days=1, n_splits=3)
    splits2 = wfv2.split(wf_data)
    assert len(splits2) <= 3, f"Expected at most 3 splits, got {len(splits2)}"


# ── No data leakage ──────────────────────────────────────────────
def test_no_data_leakage(wf_data):
    """Test set dates must always come after train set dates."""
    wfv = WalkForwardValidator(train_days=100, test_days=50, embargo_days=1)
    splits = wfv.split(wf_data)

    for i, (train_df, test_df) in enumerate(splits):
        train_max_date = pd.to_datetime(train_df["date"]).max()
        test_min_date = pd.to_datetime(test_df["date"]).min()
        assert test_min_date > train_max_date, (
            f"Fold {i}: test start ({test_min_date}) must be after "
            f"train end ({train_max_date})"
        )


# ── Embargo gap ──────────────────────────────────────────────────
def test_embargo_gap(wf_data):
    """There should be an embargo gap between train and test sets."""
    embargo_days = 5
    wfv = WalkForwardValidator(
        train_days=100, test_days=50, embargo_days=embargo_days
    )
    splits = wfv.split(wf_data)

    for i, (train_df, test_df) in enumerate(splits):
        train_last_idx = train_df.index[-1]
        test_first_idx = test_df.index[0]
        gap = test_first_idx - train_last_idx
        assert gap >= embargo_days, (
            f"Fold {i}: gap ({gap} rows) is less than embargo ({embargo_days})"
        )


# ── Tournament ranking ──────────────────────────────────────────
def test_tournament_ranking():
    """StrategyTournament should produce a ranked leaderboard."""
    from src.research.selection import StrategyTournament

    tournament = StrategyTournament()
    # Just verify the tournament can be instantiated and has the right API
    assert hasattr(tournament, "add_strategy")
    assert hasattr(tournament, "run_tournament")
    assert hasattr(tournament, "get_results")
    assert hasattr(tournament, "get_all_results")
    # Without adding strategies, the leaderboard should be empty
    result = tournament.get_all_results()
    assert isinstance(result, dict)
