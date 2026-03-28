"""
Option chain utilities for NIFTY and other F&O instruments.
"""

import logging
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


class OptionChain:
    """Utilities for filtering and analysing option chain data from NFO instruments."""

    @staticmethod
    def load_nifty_options(instruments_df, expiry=None):
        """Filter NIFTY options from an NFO instruments DataFrame.

        Args:
            instruments_df: DataFrame with NFO instrument data.
            expiry: Optional expiry date (string 'YYYY-MM-DD', datetime, or None).
                    If None, returns all expiries.

        Returns:
            DataFrame of NIFTY option instruments.
        """
        df = instruments_df.copy()

        # Ensure expiry is datetime
        if "expiry" in df.columns:
            df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")

        # Filter to NIFTY options (CE/PE) in NFO-OPT segment
        mask = (
            (df["name"] == "NIFTY")
            & (df["instrument_type"].isin(["CE", "PE"]))
            & (df["segment"] == "NFO-OPT")
        )
        options = df.loc[mask].copy()

        if expiry is not None:
            expiry_dt = pd.to_datetime(expiry)
            options = options.loc[options["expiry"] == expiry_dt]

        return options.reset_index(drop=True)

    @staticmethod
    def get_nearest_expiry(instruments_df):
        """Find the nearest weekly expiry date from NFO instruments.

        Args:
            instruments_df: DataFrame with NFO instrument data (must include
                            NIFTY options with expiry column).

        Returns:
            datetime of the nearest expiry, or None if no options found.
        """
        df = instruments_df.copy()
        if "expiry" in df.columns:
            df["expiry"] = pd.to_datetime(df["expiry"], errors="coerce")

        mask = (
            (df["name"] == "NIFTY")
            & (df["instrument_type"].isin(["CE", "PE"]))
            & (df["segment"] == "NFO-OPT")
        )
        options = df.loc[mask]

        if options.empty:
            logger.warning("No NIFTY options found in instruments data")
            return None

        today = pd.Timestamp(datetime.now().date())
        future_expiries = options.loc[options["expiry"] >= today, "expiry"].dropna().unique()

        if len(future_expiries) == 0:
            logger.warning("No future expiries found")
            return None

        nearest = min(future_expiries)
        return pd.Timestamp(nearest)

    @staticmethod
    def get_atm_strike(spot_price, instruments_df, expiry):
        """Find the ATM (at-the-money) strike closest to the spot price.

        Args:
            spot_price: Current spot price of the underlying.
            instruments_df: DataFrame with NFO instrument data.
            expiry: Expiry date (string or datetime).

        Returns:
            Float strike price closest to spot_price, or None.
        """
        options = OptionChain.load_nifty_options(instruments_df, expiry=expiry)
        if options.empty:
            return None

        strikes = options["strike"].unique()
        if len(strikes) == 0:
            return None

        # Find the strike nearest to spot
        atm_strike = min(strikes, key=lambda s: abs(s - spot_price))
        return float(atm_strike)

    @staticmethod
    def get_strikes_around_atm(spot_price, instruments_df, expiry, n=2):
        """Get ATM +/- n strikes for a given expiry.

        Args:
            spot_price: Current spot price.
            instruments_df: DataFrame with NFO instrument data.
            expiry: Expiry date.
            n: Number of strikes above and below ATM (default 2).

        Returns:
            DataFrame of option instruments for the selected strikes.
        """
        options = OptionChain.load_nifty_options(instruments_df, expiry=expiry)
        if options.empty:
            return pd.DataFrame()

        strikes = sorted(options["strike"].unique())
        if len(strikes) == 0:
            return pd.DataFrame()

        # Find ATM index
        atm_strike = min(strikes, key=lambda s: abs(s - spot_price))
        atm_idx = strikes.index(atm_strike)

        # Select range
        low = max(0, atm_idx - n)
        high = min(len(strikes), atm_idx + n + 1)
        selected_strikes = strikes[low:high]

        result = options.loc[options["strike"].isin(selected_strikes)].copy()
        return result.sort_values(["strike", "instrument_type"]).reset_index(drop=True)

    @staticmethod
    def filter_by_type(chain, option_type="CE"):
        """Filter an option chain DataFrame by option type.

        Args:
            chain: DataFrame of option instruments.
            option_type: 'CE' for calls, 'PE' for puts.

        Returns:
            Filtered DataFrame.
        """
        return chain.loc[chain["instrument_type"] == option_type].copy().reset_index(drop=True)
