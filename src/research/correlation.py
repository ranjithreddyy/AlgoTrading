"""Strategy correlation analysis utilities."""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def compute_strategy_returns(results_dict: Dict) -> pd.DataFrame:
    """Build a DataFrame of daily PnL per strategy from backtest results.

    Args:
        results_dict: Mapping of strategy_name -> BacktestResult (or dict with 'trades' list).

    Returns:
        DataFrame where each column is a strategy's daily net PnL indexed by date.
        Missing dates are filled with 0.0.
    """
    strategy_series = {}

    for name, result in results_dict.items():
        # Support both BacktestResult objects and raw dicts
        if hasattr(result, "trades"):
            trades = result.trades
        elif isinstance(result, dict):
            trades = result.get("trades", [])
        else:
            trades = []

        if not trades:
            strategy_series[name] = pd.Series(dtype=float)
            continue

        daily_pnl: Dict[str, float] = {}
        for trade in trades:
            exit_date = str(trade.get("exit_date", ""))[:10]  # YYYY-MM-DD
            if not exit_date:
                continue
            daily_pnl[exit_date] = daily_pnl.get(exit_date, 0.0) + float(trade.get("net_pnl", 0.0))

        series = pd.Series(daily_pnl, name=name)
        series.index = pd.to_datetime(series.index)
        strategy_series[name] = series

    if not strategy_series:
        return pd.DataFrame()

    returns_df = pd.DataFrame(strategy_series)
    returns_df = returns_df.sort_index()
    returns_df = returns_df.fillna(0.0)
    return returns_df


def correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Compute the pairwise Pearson correlation matrix of strategy returns.

    Args:
        returns_df: DataFrame of daily PnL per strategy (from compute_strategy_returns).

    Returns:
        Correlation matrix DataFrame (n_strategies x n_strategies).
    """
    if returns_df.empty or returns_df.shape[1] < 2:
        return pd.DataFrame()

    # Drop columns with zero variance (no trades)
    non_const = returns_df.columns[returns_df.std() > 1e-10]
    df = returns_df[non_const]

    if df.shape[1] < 2:
        return pd.DataFrame(np.ones((1, 1)), index=non_const, columns=non_const)

    corr = df.corr(method="pearson")
    return corr


def plot_correlation_heatmap(corr_matrix: pd.DataFrame, output_path: str) -> None:
    """Save a correlation heatmap PNG.

    Args:
        corr_matrix: Correlation matrix DataFrame.
        output_path: File path for the output PNG.
    """
    import os
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors

    if corr_matrix.empty:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.text(0.5, 0.5, "No correlation data", ha="center", va="center")
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        fig.savefig(output_path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        return

    n = corr_matrix.shape[0]
    fig_size = max(8, n * 1.2)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size * 0.85))

    cmap = plt.cm.RdYlGn
    norm = mcolors.Normalize(vmin=-1, vmax=1)

    im = ax.imshow(corr_matrix.values, cmap=cmap, norm=norm, aspect="auto")

    # Labels
    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha="right", fontsize=9)
    ax.set_yticklabels(corr_matrix.index, fontsize=9)

    # Annotate cells
    for i in range(n):
        for j in range(n):
            val = corr_matrix.iloc[i, j]
            color = "black" if abs(val) < 0.7 else "white"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8, color=color)

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Pearson Correlation")
    ax.set_title("Strategy Correlation Matrix", fontsize=13, fontweight="bold", pad=12)
    fig.tight_layout()

    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved correlation heatmap -> {output_path}")


def find_uncorrelated_pairs(
    corr_matrix: pd.DataFrame, threshold: float = 0.3
) -> List[Tuple[str, str]]:
    """Find pairs of strategies with low absolute correlation.

    Args:
        corr_matrix: Correlation matrix DataFrame.
        threshold: Maximum absolute correlation to consider 'uncorrelated'. Default 0.3.

    Returns:
        List of (strategy_a, strategy_b) tuples where |corr| <= threshold.
    """
    if corr_matrix.empty:
        return []

    pairs = []
    strategies = list(corr_matrix.columns)
    n = len(strategies)

    for i in range(n):
        for j in range(i + 1, n):
            corr_val = corr_matrix.iloc[i, j]
            if abs(corr_val) <= threshold:
                pairs.append((strategies[i], strategies[j]))

    return pairs


def marginal_contribution_to_risk(
    weights: np.ndarray, cov_matrix: pd.DataFrame
) -> pd.Series:
    """Compute the marginal contribution to portfolio risk for each strategy.

    Marginal risk contribution = (Cov * w)_i / portfolio_vol

    Args:
        weights: Array of portfolio weights (must sum to 1).
        cov_matrix: Covariance matrix of strategy returns (DataFrame).

    Returns:
        pd.Series of marginal risk contributions indexed by strategy names.
    """
    w = np.asarray(weights, dtype=float)
    cov = cov_matrix.values.astype(float)

    portfolio_var = float(w @ cov @ w)
    portfolio_vol = np.sqrt(max(portfolio_var, 1e-12))

    marginal = (cov @ w) / portfolio_vol
    total_risk_contrib = w * marginal

    return pd.Series(total_risk_contrib, index=cov_matrix.columns)


def diversification_score(returns_df: pd.DataFrame) -> float:
    """Compute a diversification score for the strategy set.

    Score = 1 - mean(|off-diagonal correlations|)
    1.0 means perfectly diversified (all correlations = 0).
    0.0 means all strategies are perfectly correlated.

    Args:
        returns_df: DataFrame of daily PnL per strategy.

    Returns:
        Float in [0, 1].
    """
    corr = correlation_matrix(returns_df)
    if corr.empty or corr.shape[0] < 2:
        return 1.0

    n = corr.shape[0]
    # Extract upper triangle (excluding diagonal)
    upper_idx = np.triu_indices(n, k=1)
    off_diag = corr.values[upper_idx]

    if len(off_diag) == 0:
        return 1.0

    mean_abs_corr = float(np.mean(np.abs(off_diag)))
    score = 1.0 - mean_abs_corr
    return float(np.clip(score, 0.0, 1.0))
