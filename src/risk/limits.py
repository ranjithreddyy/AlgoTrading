"""Risk limits and risk manager."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RiskLimits:
    """Configurable risk limits for the trading system."""

    max_daily_loss: float = 10_000  # INR
    max_daily_trades: int = 20
    max_consecutive_losses: int = 5
    max_notional_exposure: float = 500_000
    max_simultaneous_positions: int = 5
    max_capital_per_trade_pct: float = 0.10
    no_trade_first_minutes: int = 3  # after market open
    no_new_positions_before_close_minutes: int = 15
    force_exit_before_close_minutes: int = 5


class RiskManager:
    """Tracks daily risk metrics and enforces risk limits."""

    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
        self._daily_pnl: float = 0.0
        self._trade_count: int = 0
        self._consecutive_losses: int = 0
        self._killed: bool = False
        self._trades: List[Dict[str, Any]] = []
        self._open_positions: int = 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def trade_count(self) -> int:
        return self._trade_count

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_trade(
        self,
        signal: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """Check whether a proposed trade is allowed under current limits.

        Args:
            signal: Dict with at least 'symbol', 'side', and optionally
                'notional', 'timestamp'.
            current_state: Dict with keys such as 'open_positions',
                'notional_exposure', 'capital', 'market_open_time',
                'market_close_time', 'now'.

        Returns:
            (allowed, reason) tuple.
        """
        if self._killed:
            return False, "Risk manager is killed -- no trading allowed"

        # Daily loss limit
        if self._daily_pnl <= -abs(self.limits.max_daily_loss):
            return False, f"Daily loss limit reached ({self._daily_pnl:.2f})"

        # Daily trade count
        if self._trade_count >= self.limits.max_daily_trades:
            return False, f"Max daily trades reached ({self._trade_count})"

        # Consecutive losses
        if self._consecutive_losses >= self.limits.max_consecutive_losses:
            return False, (
                f"Max consecutive losses reached ({self._consecutive_losses})"
            )

        # Simultaneous positions
        open_positions = current_state.get("open_positions", self._open_positions)
        if open_positions >= self.limits.max_simultaneous_positions:
            return False, (
                f"Max simultaneous positions reached ({open_positions})"
            )

        # Notional exposure
        notional_exposure = current_state.get("notional_exposure", 0)
        trade_notional = signal.get("notional", 0)
        if (notional_exposure + trade_notional) > self.limits.max_notional_exposure:
            return False, (
                f"Max notional exposure would be breached "
                f"({notional_exposure + trade_notional:.2f})"
            )

        # Capital per trade percentage
        capital = current_state.get("capital", 0)
        if capital > 0 and trade_notional > 0:
            pct = trade_notional / capital
            if pct > self.limits.max_capital_per_trade_pct:
                return False, (
                    f"Trade exceeds max capital per trade "
                    f"({pct:.2%} > {self.limits.max_capital_per_trade_pct:.2%})"
                )

        # Time-based limits
        now = current_state.get("now")
        market_open = current_state.get("market_open_time")
        market_close = current_state.get("market_close_time")

        if now is not None and market_open is not None:
            minutes_since_open = (now - market_open).total_seconds() / 60
            if minutes_since_open < self.limits.no_trade_first_minutes:
                return False, (
                    f"No trading in first {self.limits.no_trade_first_minutes} "
                    f"minutes after open"
                )

        if now is not None and market_close is not None:
            minutes_to_close = (market_close - now).total_seconds() / 60
            if minutes_to_close <= self.limits.no_new_positions_before_close_minutes:
                return False, (
                    f"No new positions within "
                    f"{self.limits.no_new_positions_before_close_minutes} "
                    f"minutes of close"
                )

        return True, "OK"

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """Record a completed trade and update counters."""
        self._trades.append(trade)
        self._trade_count += 1
        pnl = trade.get("pnl", 0.0)
        self._daily_pnl += pnl

        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    def record_loss(self, amount: float) -> None:
        """Record a loss amount (positive number means loss)."""
        self._daily_pnl -= abs(amount)
        self._consecutive_losses += 1

    def is_killed(self) -> bool:
        """Return whether trading has been killed."""
        return self._killed

    def kill(self, reason: str = "manual") -> None:
        """Kill all trading."""
        self._killed = True

    def reset_daily(self) -> None:
        """Reset all daily counters (call at start of each trading day)."""
        self._daily_pnl = 0.0
        self._trade_count = 0
        self._consecutive_losses = 0
        self._killed = False
        self._trades = []
        self._open_positions = 0
