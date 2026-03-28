"""Triple-barrier labeling method.

For each bar, determine whether take-profit, stop-loss, or the maximum
holding period is reached first.  Works on both minute and daily data.
"""

import numpy as np
import pandas as pd


def triple_barrier_label(
    df: pd.DataFrame,
    take_profit: float,
    stop_loss: float,
    max_holding: int,
    price_col: str = "close",
) -> pd.Series:
    """Apply the triple-barrier method to label each bar.

    Args:
        df: DataFrame with at least a price column.
        take_profit: Fractional move up to trigger TP (e.g. 0.03 = 3%).
        stop_loss: Fractional move down to trigger SL (e.g. 0.02 = 2%).
        max_holding: Maximum number of bars to hold before time-stop.
        price_col: Column name for the reference price.

    Returns:
        Series with values:
            +1  take-profit hit first
            -1  stop-loss hit first
             0  time expired (neither barrier hit within max_holding bars)
    """
    prices = df[price_col].values
    n = len(prices)
    labels = np.zeros(n, dtype=int)

    for i in range(n):
        entry = prices[i]
        tp_price = entry * (1.0 + take_profit)
        sl_price = entry * (1.0 - stop_loss)
        end = min(i + max_holding, n - 1)

        label = 0  # default: time expired
        for j in range(i + 1, end + 1):
            p = prices[j]
            if p >= tp_price:
                label = 1
                break
            if p <= sl_price:
                label = -1
                break
        labels[i] = label

    return pd.Series(labels, index=df.index, name="barrier_label")
