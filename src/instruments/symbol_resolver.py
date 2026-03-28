"""
Convenience functions for resolving common instrument tokens.
"""

import logging
from pathlib import Path
from datetime import datetime

import pandas as pd

from src.instruments.instrument_master import InstrumentMaster, DATA_DIR

logger = logging.getLogger(__name__)

# Well-known index tokens on Zerodha
INDEX_TOKENS = {
    "NIFTY 50": 256265,
    "NIFTY BANK": 260105,
    "NIFTY IT": 259849,
    "NIFTY FIN SERVICE": 257801,
    "NIFTY MIDCAP 100": 256777,
    "NIFTY 100": 260617,
    "NIFTY NEXT 50": 270345,
    "INDIA VIX": 264969,
}


def _default_master():
    """Load the latest available NSE instrument master from disk."""
    inst_base = DATA_DIR / "raw" / "instruments"
    if not inst_base.exists():
        raise FileNotFoundError(
            f"No instrument data found at {inst_base}. "
            "Run scripts/sync_instruments.py first."
        )

    # Pick the most recent date directory
    date_dirs = sorted(
        [d for d in inst_base.iterdir() if d.is_dir()],
        reverse=True,
    )
    if not date_dirs:
        raise FileNotFoundError("No date directories under instruments/")

    latest = date_dirs[0]
    nse_path = latest / "NSE_instruments.csv"
    if not nse_path.exists():
        raise FileNotFoundError(f"NSE instrument file not found: {nse_path}")

    master = InstrumentMaster()
    master.load_from_csv(nse_path)
    return master


def resolve_nse_stock(symbol):
    """Resolve a single NSE stock symbol to its instrument_token.

    Args:
        symbol: Trading symbol, e.g. 'RELIANCE'.

    Returns:
        Integer instrument_token, or None if not found.
    """
    master = _default_master()
    return master.get_token(symbol, exchange="NSE")


def get_liquid_stocks(min_volume=None, count=30):
    """Return a list of liquid NSE EQ stocks from the instrument master.

    Since the instrument CSV does not contain volume data, this returns
    stocks sorted by lot_size ascending (proxy for large-cap / liquid names)
    filtered to segment == 'NSE' and instrument_type == 'EQ'.

    Args:
        min_volume: Not used (reserved for future live-volume filtering).
        count: Number of stocks to return (default 30).

    Returns:
        DataFrame with columns [tradingsymbol, instrument_token, name].
    """
    master = _default_master()
    df = master.df

    eq_mask = (df["segment"] == "NSE") & (df["instrument_type"] == "EQ")
    eq = df.loc[eq_mask].copy()

    if eq.empty:
        logger.warning("No NSE EQ instruments found")
        return pd.DataFrame(columns=["tradingsymbol", "instrument_token", "name"])

    # Sort by lot_size ascending as a rough liquidity proxy, then alphabetical
    eq = eq.sort_values(["lot_size", "tradingsymbol"], ascending=[True, True])
    result = eq.head(count)[["tradingsymbol", "instrument_token", "name"]].reset_index(drop=True)
    return result


def resolve_index(name):
    """Resolve an index name to its instrument_token.

    Uses a built-in lookup table for well-known indices.
    Falls back to searching the instrument master.

    Args:
        name: Index name, e.g. 'NIFTY 50', 'NIFTY BANK'.

    Returns:
        Integer instrument_token, or None if not found.
    """
    name_upper = name.upper()

    # Check known tokens first
    if name_upper in INDEX_TOKENS:
        return INDEX_TOKENS[name_upper]

    # Fallback: search instrument master
    try:
        master = _default_master()
        token = master.get_token(name, exchange="NSE")
        if token is not None:
            return token
    except FileNotFoundError:
        pass

    logger.warning("Could not resolve index: %s", name)
    return None
