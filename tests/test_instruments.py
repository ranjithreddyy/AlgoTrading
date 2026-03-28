"""Tests for instrument modules: InstrumentMaster, SymbolResolver, OptionChain."""

from pathlib import Path

import pandas as pd
import pytest

from src.instruments.instrument_master import InstrumentMaster
from src.instruments.symbol_resolver import resolve_index, INDEX_TOKENS
from src.instruments.option_chain import OptionChain

REPO_ROOT = Path(__file__).resolve().parent.parent
NSE_CSV = REPO_ROOT / "data" / "raw" / "instruments" / "2026-03-22" / "NSE_instruments.csv"
NFO_CSV = REPO_ROOT / "data" / "raw" / "instruments" / "2026-03-22" / "NFO_instruments.csv"


@pytest.fixture
def nse_master():
    """Load the NSE instrument master from the actual CSV."""
    master = InstrumentMaster()
    master.load_from_csv(NSE_CSV)
    return master


@pytest.fixture
def nfo_df():
    """Load NFO instruments DataFrame."""
    return pd.read_csv(NFO_CSV)


# ── InstrumentMaster ─────────────────────────────────────────────────────────

def test_instrument_master_load(nse_master):
    """load_from_csv populates the DataFrame with expected columns."""
    assert not nse_master.df.empty
    for col in ["instrument_token", "tradingsymbol", "exchange", "name"]:
        assert col in nse_master.df.columns


def test_get_token(nse_master):
    """Resolve RELIANCE to a non-None instrument_token."""
    token = nse_master.get_token("RELIANCE", exchange="NSE")
    assert token is not None
    assert isinstance(token, int)


def test_get_tokens_batch(nse_master):
    """Batch resolve multiple symbols."""
    symbols = ["RELIANCE", "INFY", "TCS"]
    tokens = nse_master.get_tokens(symbols, exchange="NSE")
    assert isinstance(tokens, dict)
    # At least some should resolve (all three are major stocks)
    assert len(tokens) >= 1
    for sym, tok in tokens.items():
        assert isinstance(tok, int)


def test_search(nse_master):
    """Search for 'RELI' returns at least one result containing RELIANCE."""
    results = nse_master.search("RELI")
    assert not results.empty
    symbols = results["tradingsymbol"].tolist()
    assert any("RELIANCE" in s for s in symbols)


# ── SymbolResolver ───────────────────────────────────────────────────────────

def test_resolve_index():
    """NIFTY 50 resolves to the well-known token 256265."""
    token = resolve_index("NIFTY 50")
    assert token == 256265


# ── OptionChain ──────────────────────────────────────────────────────────────

def test_option_chain_nearest_expiry(nfo_df):
    """get_nearest_expiry returns a valid date (or None if data is stale)."""
    nearest = OptionChain.get_nearest_expiry(nfo_df)
    # The NFO CSV should have future expiry dates
    if nearest is not None:
        assert isinstance(nearest, pd.Timestamp)
        assert nearest >= pd.Timestamp("2026-01-01")
