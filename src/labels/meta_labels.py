"""Meta-labeling utilities.

Meta-labels are used to train a secondary (meta) model that decides whether
to act on a primary model's signal.  The label is 1 if the primary signal
would have been profitable, 0 otherwise.
"""

import pandas as pd


def meta_label(
    primary_signal: pd.Series,
    returns: pd.Series,
) -> pd.Series:
    """Create meta-labels from a primary signal and forward returns.

    For each bar where the primary model issues a signal (non-zero value),
    the meta-label is:
        1  if signal direction agrees with return direction (profitable trade)
        0  otherwise

    Bars where the primary signal is 0 (no trade) receive NaN.

    Args:
        primary_signal: Series of signals (e.g. +1 for long, -1 for short,
                        0 for no signal).
        returns: Series of forward returns corresponding to the same index.

    Returns:
        Series of meta-labels (1 = take the trade, 0 = skip it, NaN = no signal).
    """
    meta = pd.Series(index=primary_signal.index, dtype=float)
    meta[:] = float("nan")

    mask = primary_signal != 0
    # Profitable when signal and return have the same sign
    agreement = (primary_signal[mask] * returns[mask]) > 0
    meta.loc[mask] = agreement.astype(int)

    meta.name = "meta_label"
    return meta
