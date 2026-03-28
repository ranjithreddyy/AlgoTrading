"""Tests for core modules: enums, clock, calendar."""

from datetime import date, datetime, timedelta, timezone

from src.core.enums import (
    Exchange,
    Interval,
    OrderSide,
    OrderType,
    ProductType,
    StrategyFamily,
)
from src.core.clock import IST, current_ist, is_market_open
from src.core.calendar import NSECalendar


# ── Enums ────────────────────────────────────────────────────────────────────

def test_enums_values():
    """Verify string values of key enum members."""
    assert Exchange.NSE == "NSE"
    assert Exchange.NFO == "NFO"
    assert Exchange.BSE == "BSE"
    assert Interval.DAY == "day"
    assert Interval.MINUTE == "minute"
    assert Interval.FIFTEEN_MINUTE == "15minute"
    assert OrderSide.BUY == "BUY"
    assert OrderSide.SELL == "SELL"
    assert OrderType.MARKET == "MARKET"
    assert OrderType.LIMIT == "LIMIT"
    assert ProductType.MIS == "MIS"
    assert ProductType.CNC == "CNC"
    assert StrategyFamily.MOMENTUM_BREAKOUT == "MOMENTUM_BREAKOUT"
    assert StrategyFamily.MEAN_REVERSION == "MEAN_REVERSION"


# ── Clock ────────────────────────────────────────────────────────────────────

def test_clock_ist():
    """current_ist() returns a datetime with IST timezone (UTC+5:30)."""
    now = current_ist()
    assert now.tzinfo is not None
    utc_offset = now.utcoffset()
    assert utc_offset == timedelta(hours=5, minutes=30)


def test_clock_market_hours():
    """is_market_open correctly identifies open vs closed times."""
    # Wednesday 10:00 IST -> market open
    open_time = datetime(2026, 3, 18, 10, 0, 0, tzinfo=IST)
    assert is_market_open(open_time) is True

    # Wednesday 8:00 IST -> before market open
    early_time = datetime(2026, 3, 18, 8, 0, 0, tzinfo=IST)
    assert is_market_open(early_time) is False

    # Wednesday 16:00 IST -> after market close
    late_time = datetime(2026, 3, 18, 16, 0, 0, tzinfo=IST)
    assert is_market_open(late_time) is False

    # Saturday 10:00 IST -> weekend
    weekend_time = datetime(2026, 3, 21, 10, 0, 0, tzinfo=IST)
    assert is_market_open(weekend_time) is False


# ── Calendar ─────────────────────────────────────────────────────────────────

def test_calendar_weekends():
    """Weekends are not trading days."""
    cal = NSECalendar()
    saturday = date(2026, 3, 21)  # Saturday
    sunday = date(2026, 3, 22)    # Sunday
    assert cal.is_trading_day(saturday) is False
    assert cal.is_trading_day(sunday) is False


def test_calendar_holidays():
    """Known NSE holidays are not trading days."""
    cal = NSECalendar()
    # Republic Day 2026
    assert cal.is_trading_day(date(2026, 1, 26)) is False
    # Independence Day 2026
    assert cal.is_trading_day(date(2026, 8, 15)) is False
    # Christmas 2026
    assert cal.is_trading_day(date(2026, 12, 25)) is False
    # A normal weekday should be a trading day
    assert cal.is_trading_day(date(2026, 3, 16)) is True  # Monday


def test_calendar_expiry():
    """Thursdays that are trading days should be expiry days."""
    cal = NSECalendar()
    # March 19, 2026 is a Thursday
    thursday = date(2026, 3, 19)
    assert thursday.weekday() == 3
    assert cal.is_expiry_day(thursday) is True

    # Non-Thursday is not an expiry day
    wednesday = date(2026, 3, 18)
    assert cal.is_expiry_day(wednesday) is False


def test_calendar_trading_days_between():
    """Count of trading days between two dates matches expectation."""
    cal = NSECalendar()
    # Mon Mar 16 to Fri Mar 20, 2026: 5 weekdays, check for holidays
    start = date(2026, 3, 16)
    end = date(2026, 3, 20)
    count = cal.trading_days_between(start, end)
    # Mar 20 is Id-Ul-Fitr holiday -> 4 trading days
    assert count == 4


def test_calendar_next_prev():
    """next/prev trading day skips weekends and holidays."""
    cal = NSECalendar()
    # Friday Mar 20, 2026 is Id-Ul-Fitr (holiday)
    friday_holiday = date(2026, 3, 20)
    assert cal.is_trading_day(friday_holiday) is False

    # Previous trading day from Saturday March 21 should skip Sat + Fri holiday
    prev_day = cal.prev_trading_day(date(2026, 3, 21))
    assert prev_day == date(2026, 3, 19)  # Thursday

    # Next trading day from Friday March 20 (holiday) should be Monday March 23
    next_day = cal.next_trading_day(friday_holiday)
    assert next_day == date(2026, 3, 23)
