"""Cross-asset features for multi-instrument analysis.

Functions for computing relationships between different instruments.
"""

import numpy as np
import pandas as pd


def rolling_correlation(df1, df2, period=20):
    """Rolling correlation between two price series.

    Args:
        df1: DataFrame with 'close' column.
        df2: DataFrame with 'close' column.
        period: Rolling window size (default 20).

    Returns:
        pd.Series of rolling correlations.
    """
    ret1 = df1["close"].pct_change()
    ret2 = df2["close"].pct_change()
    return ret1.rolling(period).corr(ret2).rename("rolling_correlation")


def rolling_beta(stock_df, index_df, period=60):
    """Rolling beta of a stock versus an index.

    Beta = Cov(stock, index) / Var(index), computed on returns.

    Args:
        stock_df: DataFrame with 'close' column for the stock.
        index_df: DataFrame with 'close' column for the index.
        period: Rolling window size (default 60).

    Returns:
        pd.Series of rolling beta values.
    """
    stock_ret = stock_df["close"].pct_change()
    index_ret = index_df["close"].pct_change()

    cov = stock_ret.rolling(period).cov(index_ret)
    var = index_ret.rolling(period).var()

    beta = (cov / var).replace([np.inf, -np.inf], np.nan)
    return beta.rename("rolling_beta")


def relative_strength(stock_df, index_df, period=20):
    """Relative strength: stock cumulative return / index cumulative return.

    Args:
        stock_df: DataFrame with 'close' column.
        index_df: DataFrame with 'close' column.
        period: Lookback period for cumulative returns (default 20).

    Returns:
        pd.Series of relative strength ratios.
    """
    stock_ret = stock_df["close"].pct_change(period)
    index_ret = index_df["close"].pct_change(period)

    rs = ((1 + stock_ret) / (1 + index_ret)).replace([np.inf, -np.inf], np.nan)
    return rs.rename("relative_strength")


def dispersion_score(stock_dfs, period=20):
    """Cross-sectional standard deviation of returns.

    Args:
        stock_dfs: Dict of symbol -> DataFrame, each with 'close' column.
        period: Return period for computing dispersion (default 20).

    Returns:
        pd.Series of cross-sectional dispersion values.
    """
    returns = {}
    for symbol, df in stock_dfs.items():
        returns[symbol] = df["close"].pct_change(period)

    returns_df = pd.DataFrame(returns)
    return returns_df.std(axis=1).rename("dispersion_score")


def cross_sectional_rank(stock_dfs, metric="returns"):
    """Rank each stock cross-sectionally on a given metric.

    Args:
        stock_dfs: Dict of symbol -> DataFrame, each with 'close' column.
        metric: Metric to rank on. Currently supports 'returns' (1-period).

    Returns:
        pd.DataFrame with one column per symbol containing percentile ranks (0-1).
    """
    values = {}
    for symbol, df in stock_dfs.items():
        if metric == "returns":
            values[symbol] = df["close"].pct_change()
        else:
            values[symbol] = df["close"].pct_change()

    values_df = pd.DataFrame(values)
    ranked = values_df.rank(axis=1, pct=True)
    return ranked
