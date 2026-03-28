"""
NSE Trading Calendar

Provides utilities for determining trading days, holidays, and expiry dates
on the National Stock Exchange of India.
"""

from datetime import date, timedelta
from typing import List


# NSE holidays for 2025 (official NSE holiday list)
NSE_HOLIDAYS_2025 = [
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-Ul-Fitr (Ramadan Eid)
    date(2025, 4, 10),   # Shri Mahavir Jayanti
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 6, 7),    # Bakri Id (Eid al-Adha)
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 16),   # Ashura
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Mahatma Gandhi Jayanti
    date(2025, 10, 21),  # Diwali (Laxmi Puja)
    date(2025, 10, 22),  # Diwali Balipratipada
    date(2025, 11, 5),   # Guru Nanak Jayanti (Prakash Gurpurb)
    date(2025, 12, 25),  # Christmas
]

# NSE holidays for 2026 (projected based on typical NSE holiday patterns)
NSE_HOLIDAYS_2026 = [
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 17),   # Mahashivratri
    date(2026, 3, 3),    # Holi
    date(2026, 3, 20),   # Id-Ul-Fitr (Ramadan Eid)
    date(2026, 3, 30),   # Shri Mahavir Jayanti
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 27),   # Bakri Id (Eid al-Adha)
    date(2026, 6, 26),   # Muharram
    date(2026, 8, 15),   # Independence Day
    date(2026, 8, 17),   # Ganesh Chaturthi (Vinayaka Chaturthi)
    date(2026, 10, 2),   # Mahatma Gandhi Jayanti
    date(2026, 10, 9),   # Dussehra
    date(2026, 10, 29),  # Diwali (Laxmi Puja)
    date(2026, 10, 30),  # Diwali Balipratipada
    date(2026, 11, 25),  # Guru Nanak Jayanti
    date(2026, 12, 25),  # Christmas
]

# Combined set for fast lookup
_ALL_HOLIDAYS = set(NSE_HOLIDAYS_2025 + NSE_HOLIDAYS_2026)


class NSECalendar:
    """NSE (National Stock Exchange of India) trading calendar."""

    def __init__(self):
        self.holidays = _ALL_HOLIDAYS

    def is_trading_day(self, d: date) -> bool:
        """Return True if the given date is a trading day (not weekend, not holiday)."""
        if d.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        if d in self.holidays:
            return False
        return True

    def next_trading_day(self, d: date) -> date:
        """Return the next trading day after the given date."""
        current = d + timedelta(days=1)
        while not self.is_trading_day(current):
            current += timedelta(days=1)
        return current

    def prev_trading_day(self, d: date) -> date:
        """Return the previous trading day before the given date."""
        current = d - timedelta(days=1)
        while not self.is_trading_day(current):
            current -= timedelta(days=1)
        return current

    def is_expiry_day(self, d: date) -> bool:
        """Check if the date is a weekly NIFTY expiry day (Thursday and a trading day)."""
        return d.weekday() == 3 and self.is_trading_day(d)

    def is_monthly_expiry(self, d: date) -> bool:
        """Check if the date is the last Thursday of the month (monthly expiry).

        If the last Thursday is a holiday, the expiry shifts to the previous
        trading day, but this method strictly checks for last-Thursday status.
        """
        if d.weekday() != 3:
            return False
        # Check if there is another Thursday in this month
        next_thursday = d + timedelta(days=7)
        if next_thursday.month == d.month:
            return False
        return self.is_trading_day(d)

    def trading_days_between(self, start: date, end: date) -> int:
        """Count the number of trading days between start and end (inclusive)."""
        return len(self.get_trading_days(start, end))

    def get_trading_days(self, start: date, end: date) -> List[date]:
        """Return a list of all trading days between start and end (inclusive)."""
        days = []
        current = start
        while current <= end:
            if self.is_trading_day(current):
                days.append(current)
            current += timedelta(days=1)
        return days
