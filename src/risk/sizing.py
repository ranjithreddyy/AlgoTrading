"""Position sizing utilities."""

import math


def fixed_quantity(capital: float, price: float, pct: float = 0.02) -> int:
    """Calculate position size risking *pct* of capital per trade.

    Args:
        capital: Total available capital (INR).
        price: Current price per share.
        pct: Fraction of capital to risk (default 2%).

    Returns:
        Number of shares (integer, floored).
    """
    if price <= 0:
        return 0
    risk_amount = capital * pct
    qty = int(risk_amount / price)
    return max(qty, 0)


def kelly_fraction(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Compute the Kelly criterion fraction.

    f* = (p * b - q) / b
    where p = win_rate, q = 1 - p, b = avg_win / avg_loss

    Args:
        win_rate: Historical win probability (0-1).
        avg_win: Average winning trade profit.
        avg_loss: Average losing trade loss (positive number).

    Returns:
        Optimal fraction of capital to allocate (can be negative if edge is
        negative; caller should clamp to 0).
    """
    if avg_loss <= 0 or avg_win <= 0:
        return 0.0
    b = avg_win / avg_loss
    q = 1.0 - win_rate
    fraction = (win_rate * b - q) / b
    return round(fraction, 6)


def volatility_adjusted_size(
    capital: float,
    price: float,
    atr: float,
    risk_per_trade: float = 0.01,
) -> int:
    """Position size adjusted for volatility (ATR-based).

    Determines how many shares to buy so that a 1-ATR adverse move equals
    *risk_per_trade* fraction of capital.

    Args:
        capital: Total available capital (INR).
        price: Current price per share.
        atr: Average True Range of the instrument.
        risk_per_trade: Fraction of capital to risk per trade (default 1%).

    Returns:
        Number of shares (integer, floored).
    """
    if atr <= 0 or price <= 0:
        return 0
    risk_amount = capital * risk_per_trade
    qty = int(risk_amount / atr)
    return max(qty, 0)


def max_position_size(capital: float, price: float, max_pct: float = 0.10) -> int:
    """Maximum position size -- never exceed *max_pct* of capital.

    Args:
        capital: Total available capital (INR).
        price: Current price per share.
        max_pct: Maximum fraction of capital in a single position (default 10%).

    Returns:
        Maximum number of shares (integer, floored).
    """
    if price <= 0:
        return 0
    max_notional = capital * max_pct
    qty = int(max_notional / price)
    return max(qty, 0)
