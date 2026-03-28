"""Gamma Scalp Strategy - Expiry-day fast mean reversion with tight stops."""

from typing import List, Optional

from src.strategies.base import Strategy, StrategyConfig


class GammaScalpStrategy(Strategy):
    """Expiry-Day Gamma Scalp: scalps rapid moves as gamma increases on expiry days.
    Fast mean reversion with very tight stops and targets. Uses short-period RSI
    combined with bar range expansion as entry signal. Designed for very short
    holding periods."""

    __strategy_name__ = "gamma_scalp"
    __default_family__ = "options"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._closes: List[float] = []
        self._ranges: List[float] = []  # high - low per bar
        self._in_position: bool = False
        self._entry_price: float = 0.0
        self._position_side: Optional[str] = None
        self._bar_count: int = 0
        self._entry_bar: int = 0

    def get_default_params(self) -> dict:
        return {
            "rsi_period": 5,
            "rsi_upper": 65,
            "rsi_lower": 35,
            "stop_pct": 0.005,
            "target_pct": 0.01,
            "range_expansion_mult": 1.5,
            "max_holding_bars": 5,
        }

    def get_param_grid(self) -> dict:
        return {
            "rsi_period": [3, 5, 7],
            "rsi_upper": [60, 65, 70],
            "rsi_lower": [30, 35, 40],
            "stop_pct": [0.003, 0.005, 0.007],
            "target_pct": [0.007, 0.01, 0.015],
            "range_expansion_mult": [1.3, 1.5, 2.0],
            "max_holding_bars": [3, 5, 8],
        }

    @staticmethod
    def _compute_rsi(closes: List[float], period: int) -> Optional[float]:
        """Compute RSI from the last (period + 1) closes."""
        if len(closes) < period + 1:
            return None
        changes = [closes[i] - closes[i - 1] for i in range(-period, 0)]
        gains = [c for c in changes if c > 0]
        losses = [-c for c in changes if c < 0]
        avg_gain = sum(gains) / period if gains else 0.0
        avg_loss = sum(losses) / period if losses else 0.0
        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        high = bar["high"]
        low = bar["low"]
        bar_range = high - low
        self._bar_count += 1

        self._closes.append(close)
        self._ranges.append(bar_range)

        rsi_period = self.p["rsi_period"]

        if len(self._closes) < rsi_period + 1:
            return None

        rsi = self._compute_rsi(self._closes, rsi_period)
        if rsi is None:
            return None

        # Check bar range expansion (current range vs average of recent ranges)
        lookback = min(20, len(self._ranges) - 1)
        avg_range = (
            sum(self._ranges[-lookback - 1 : -1]) / lookback
            if lookback > 0
            else bar_range
        )
        range_expanded = bar_range >= avg_range * self.p["range_expansion_mult"]

        # If in position, check for quick exit
        if self._in_position:
            bars_held = self._bar_count - self._entry_bar

            # Max holding period (very short for gamma scalp)
            if bars_held >= self.p["max_holding_bars"]:
                action = "sell" if self._position_side == "long" else "buy"
                self._in_position = False
                self._position_side = None
                return {"action": action, "price": close, "reason": "gamma scalp max hold exit"}

            # Mean reversion exit: RSI reverts toward neutral
            if self._position_side == "long" and rsi >= 50:
                self._in_position = False
                self._position_side = None
                return {"action": "sell", "price": close, "reason": f"RSI={rsi:.0f} reverted to neutral - exit long"}

            if self._position_side == "short" and rsi <= 50:
                self._in_position = False
                self._position_side = None
                return {"action": "buy", "price": close, "reason": f"RSI={rsi:.0f} reverted to neutral - exit short"}

            return None

        # Entry: Fast RSI oversold + range expansion -> buy CE (go long, quick bounce)
        if rsi <= self.p["rsi_lower"] and range_expanded:
            self._in_position = True
            self._entry_price = close
            self._entry_bar = self._bar_count
            self._position_side = "long"
            return {
                "action": "buy",
                "price": close,
                "reason": f"RSI={rsi:.0f} oversold + range expansion -> gamma scalp long",
                "side": "BUY",
                "option_type": "CE",
            }

        # Entry: Fast RSI overbought + range expansion -> buy PE (go short, quick fade)
        if rsi >= self.p["rsi_upper"] and range_expanded:
            self._in_position = True
            self._entry_price = close
            self._entry_bar = self._bar_count
            self._position_side = "short"
            return {
                "action": "sell",
                "price": close,
                "reason": f"RSI={rsi:.0f} overbought + range expansion -> gamma scalp short",
                "side": "BUY",
                "option_type": "PE",
            }

        return None

    def reset(self):
        super().reset()
        self._closes = []
        self._ranges = []
        self._in_position = False
        self._entry_price = 0.0
        self._position_side = None
        self._bar_count = 0
        self._entry_bar = 0
