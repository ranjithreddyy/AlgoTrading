"""Market clock utilities for IST trading hours."""

from datetime import datetime, time, timedelta, timezone

# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))

_MARKET_OPEN = time(9, 15)
_MARKET_CLOSE = time(15, 30)
_PREMARKET_START = time(9, 0)
_PREMARKET_END = time(9, 8)
_CLOSING_START = time(15, 30)
_CLOSING_END = time(15, 40)


def current_ist() -> datetime:
    """Return current datetime in IST."""
    return datetime.now(IST)


def is_market_open(now: datetime | None = None) -> bool:
    """Check if the market is open (9:15-15:30 IST, weekdays only)."""
    now = now or current_ist()
    now = now.astimezone(IST)
    # Monday=0 ... Friday=4
    if now.weekday() > 4:
        return False
    t = now.time()
    return _MARKET_OPEN <= t < _MARKET_CLOSE


def is_premarket(now: datetime | None = None) -> bool:
    """Check if we are in pre-market window (9:00-9:08 IST)."""
    now = now or current_ist()
    now = now.astimezone(IST)
    if now.weekday() > 4:
        return False
    t = now.time()
    return _PREMARKET_START <= t < _PREMARKET_END


def is_closing_session(now: datetime | None = None) -> bool:
    """Check if we are in closing session (15:30-15:40 IST)."""
    now = now or current_ist()
    now = now.astimezone(IST)
    if now.weekday() > 4:
        return False
    t = now.time()
    return _CLOSING_START <= t < _CLOSING_END


def time_to_close(now: datetime | None = None) -> timedelta:
    """Return timedelta until 15:30 IST today. Negative if already past."""
    now = now or current_ist()
    now = now.astimezone(IST)
    close_dt = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return close_dt - now
