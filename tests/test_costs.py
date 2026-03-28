"""Tests for the Indian trading cost model."""

import pytest

from src.backtests.costs import IndianCostModel


@pytest.fixture
def cost_model():
    return IndianCostModel()


# ── Equity intraday cost components ──────────────────────────────
def test_equity_intraday_cost_components(cost_model):
    """All expected cost components should be present."""
    costs = cost_model.calculate_equity_intraday_costs(100.0, 100, "buy")
    expected_keys = {"turnover", "brokerage", "stt", "txn_charges", "gst", "sebi", "stamp_duty", "total"}
    assert expected_keys == set(costs.keys()), f"Missing keys: {expected_keys - set(costs.keys())}"


# ── STT sell-side only (intraday) ────────────────────────────────
def test_stt_sell_side_only(cost_model):
    """For equity intraday, STT should be charged only on the sell side."""
    buy = cost_model.calculate_equity_intraday_costs(500.0, 100, "buy")
    sell = cost_model.calculate_equity_intraday_costs(500.0, 100, "sell")
    assert buy["stt"] == 0.0, "STT should be 0 on buy side for intraday"
    assert sell["stt"] > 0.0, "STT should be positive on sell side for intraday"


# ── Stamp duty buy-side only ────────────────────────────────────
def test_stamp_duty_buy_side_only(cost_model):
    """Stamp duty should only be charged on the buy side."""
    buy = cost_model.calculate_equity_intraday_costs(500.0, 100, "buy")
    sell = cost_model.calculate_equity_intraday_costs(500.0, 100, "sell")
    assert buy["stamp_duty"] > 0.0, "Stamp duty should be positive on buy"
    assert sell["stamp_duty"] == 0.0, "Stamp duty should be 0 on sell"


# ── Brokerage cap ───────────────────────────────────────────────
def test_brokerage_cap(cost_model):
    """Brokerage must never exceed Rs 20."""
    # Large order that would exceed Rs 20 without a cap
    costs = cost_model.calculate_equity_intraday_costs(5000.0, 10000, "buy")
    assert costs["brokerage"] <= 20.0, f"Brokerage {costs['brokerage']} exceeds cap"


# ── Round-trip positive ──────────────────────────────────────────
def test_round_trip_positive(cost_model):
    """Total round-trip cost must always be positive."""
    rt = cost_model.total_round_trip_cost(
        entry_price=100.0, exit_price=105.0, qty=50
    )
    assert rt["total"] > 0, "Round-trip cost must be positive"


# ── Option costs ─────────────────────────────────────────────────
def test_option_costs(cost_model):
    """Option cost calculation should work and return all components."""
    costs = cost_model.calculate_option_costs(
        premium=150.0, qty=1, lot_size=50, side="buy"
    )
    assert "total" in costs
    assert costs["total"] > 0, "Option trade cost must be positive"
    assert costs["brokerage"] == 20.0, "Option brokerage should be Rs 20 flat"
