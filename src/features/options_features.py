"""Options-specific features for F&O analysis.

Functions for computing features related to options pricing, volume, and OI.
"""

import numpy as np
import pandas as pd


def moneyness(spot, strike):
    """Compute moneyness as S/K ratio.

    Args:
        spot: Spot price (scalar or Series).
        strike: Strike price (scalar or Series).

    Returns:
        Moneyness ratio (same type as inputs).
    """
    return spot / strike


def time_to_expiry_days(current_date, expiry_date):
    """Compute number of calendar days to expiry.

    Args:
        current_date: Current date (datetime, string, or Series).
        expiry_date: Expiry date (datetime, string, or Series).

    Returns:
        int or Series: Number of days to expiry.
    """
    current = pd.to_datetime(current_date)
    expiry = pd.to_datetime(expiry_date)
    diff = expiry - current
    if isinstance(diff, pd.Timedelta):
        return max(diff.days, 0)
    return diff.dt.days.clip(lower=0)


def premium_percentile(premium, historical_premiums, period=20):
    """Compute where current premium ranks in recent history.

    Args:
        premium: Current premium value (scalar).
        historical_premiums: Series of historical premium values.
        period: Lookback period (default 20).

    Returns:
        float: Percentile rank (0 to 1).
    """
    recent = historical_premiums.tail(period)
    if len(recent) == 0:
        return np.nan
    rank = (recent < premium).sum() / len(recent)
    return rank


def put_call_ratio(put_volume, call_volume):
    """Compute put-call ratio.

    Args:
        put_volume: Put option volume (scalar or Series).
        call_volume: Call option volume (scalar or Series).

    Returns:
        PCR value. Returns NaN if call_volume is zero.
    """
    if isinstance(call_volume, pd.Series):
        return (put_volume / call_volume).replace([np.inf, -np.inf], np.nan).rename("pcr")
    if call_volume == 0:
        return np.nan
    return put_volume / call_volume


def oi_change(current_oi, prev_oi):
    """Compute change in open interest.

    Args:
        current_oi: Current open interest (scalar or Series).
        prev_oi: Previous open interest (scalar or Series).

    Returns:
        Change in OI.
    """
    return current_oi - prev_oi


def volume_oi_ratio(volume, oi):
    """Compute volume to open interest ratio.

    Args:
        volume: Trading volume (scalar or Series).
        oi: Open interest (scalar or Series).

    Returns:
        Volume/OI ratio. Returns NaN if OI is zero.
    """
    if isinstance(oi, pd.Series):
        return (volume / oi).replace([np.inf, -np.inf], np.nan).rename("volume_oi_ratio")
    if oi == 0:
        return np.nan
    return volume / oi


def straddle_premium(atm_call_premium, atm_put_premium):
    """Compute ATM straddle cost.

    Args:
        atm_call_premium: ATM call option premium (scalar or Series).
        atm_put_premium: ATM put option premium (scalar or Series).

    Returns:
        Total straddle premium.
    """
    return atm_call_premium + atm_put_premium
