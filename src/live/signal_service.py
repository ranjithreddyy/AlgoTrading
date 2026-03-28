"""Real-time signal generation from strategies."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """A trading signal produced by a strategy."""
    strategy_name: str
    symbol: str
    action: str          # "buy" or "sell"
    price: float
    reason: str
    timestamp: datetime
    accepted: bool = True
    reject_reason: str = ""

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy_name,
            "symbol": self.symbol,
            "action": self.action,
            "price": self.price,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "accepted": self.accepted,
            "reject_reason": self.reject_reason,
        }


class SignalService:
    """Run all active strategies on each new bar and collect signals."""

    def __init__(
        self,
        strategies: List[Strategy],
        max_signals_per_bar: int = 5,
    ):
        self.strategies = strategies
        self.max_signals_per_bar = max_signals_per_bar
        self.all_signals: List[Signal] = []
        self._contexts: Dict[str, dict] = {}  # per-strategy context

    def set_context(self, strategy_name: str, context: dict) -> None:
        """Set context (e.g. current position) for a specific strategy."""
        self._contexts[strategy_name] = context

    def on_bar(self, symbol: str, bar: dict) -> List[Signal]:
        """Run all strategies on *bar* and return generated signals.

        Args:
            symbol: The instrument symbol (e.g. "RELIANCE").
            bar: OHLCV bar dict with keys: date, open, high, low, close, volume.

        Returns:
            List of Signal objects (both accepted and rejected).
        """
        signals: List[Signal] = []
        now = datetime.now()

        for strategy in self.strategies:
            name = strategy.config.name
            ctx = self._contexts.get(name, {"position": None})

            try:
                raw = strategy.on_bar(bar, ctx)
            except Exception:
                logger.exception("Strategy %s raised on bar %s", name, bar.get("date"))
                continue

            if raw is None:
                continue

            sig = Signal(
                strategy_name=name,
                symbol=symbol,
                action=raw["action"],
                price=raw["price"],
                reason=raw.get("reason", ""),
                timestamp=now,
            )

            # Basic risk filter: cap signals per bar
            accepted_count = sum(1 for s in signals if s.accepted)
            if accepted_count >= self.max_signals_per_bar:
                sig.accepted = False
                sig.reject_reason = "max_signals_per_bar exceeded"

            signals.append(sig)
            self.all_signals.append(sig)

            status = "ACCEPTED" if sig.accepted else f"REJECTED ({sig.reject_reason})"
            logger.info(
                "Signal [%s] %s %s @ %.2f (%s) — %s",
                name, sig.action.upper(), symbol, sig.price, sig.reason, status,
            )

        return signals

    def get_signal_log(self, last_n: int = 50) -> List[dict]:
        """Return the last N signals as dicts."""
        return [s.as_dict() for s in self.all_signals[-last_n:]]
