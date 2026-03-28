"""Convenience function for computing features."""

from typing import List, Optional

import pandas as pd

from src.features.feature_registry import default_registry


def compute_features(
    df: pd.DataFrame,
    feature_names: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Compute all (or selected) features for a given OHLCV dataframe.

    Handles NaN filling: forward fill then drop leading NaN rows.

    Args:
        df: DataFrame with columns: date, open, high, low, close, volume.
        feature_names: Optional list of feature names to compute. If None,
                       computes all registered features.

    Returns:
        DataFrame with computed features as columns. Leading NaN rows are
        dropped after forward-filling.
    """
    if feature_names is not None:
        features = default_registry.compute_selected(df, feature_names)
    else:
        features = default_registry.compute_all(df)

    # Forward fill then drop rows that still have NaNs at the start
    features = features.ffill()
    # Find first row where all values are non-NaN
    first_valid = features.dropna(how="any").index.min()
    if first_valid is not None:
        features = features.loc[first_valid:]

    return features
