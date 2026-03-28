"""Forward-looking return labeling utilities."""

import numpy as np
import pandas as pd
from typing import List


def forward_returns(
    df: pd.DataFrame,
    horizons: List[int] = [1, 5, 10, 20],
    price_col: str = "close",
) -> pd.DataFrame:
    """Compute forward-looking returns at each horizon.

    Args:
        df: DataFrame with a price column (default 'close').
        horizons: List of forward periods (in bars).
        price_col: Column to use for price.

    Returns:
        DataFrame with columns 'fwd_ret_{h}' for each horizon h.
    """
    prices = df[price_col].values
    result = pd.DataFrame(index=df.index)
    for h in horizons:
        fwd = np.empty(len(prices))
        fwd[:] = np.nan
        fwd[: len(prices) - h] = prices[h:] / prices[: len(prices) - h] - 1.0
        result[f"fwd_ret_{h}"] = fwd
    return result


def return_buckets(
    returns: pd.Series,
    n_buckets: int = 3,
) -> pd.Series:
    """Classify returns into equal-frequency buckets.

    Args:
        returns: Series of return values.
        n_buckets: Number of buckets (default 3: negative / neutral / positive).

    Returns:
        Series of integer bucket labels (0 = lowest, n_buckets-1 = highest).
    """
    labels = list(range(n_buckets))
    return pd.qcut(returns, q=n_buckets, labels=labels, duplicates="drop").astype(int)


def binary_label(
    returns: pd.Series,
    threshold: float = 0.0,
) -> pd.Series:
    """Binary label: 1 if return > threshold, 0 otherwise.

    Args:
        returns: Series of return values.
        threshold: Cut-off value.

    Returns:
        Series of 0/1 integers.
    """
    return (returns > threshold).astype(int)
