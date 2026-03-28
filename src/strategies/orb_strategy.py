"""Opening Range Breakout Strategy.

For daily data: uses the first N bars to define the range, then trades the breakout.
"""

from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy, StrategyConfig


class ORBStrategy(Strategy):
    """Opening Range Breakout - first N bars define range, trade breakout."""

    __strategy_name__ = "orb_strategy"
    __default_family__ = "momentum"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._bar_count = 0
        self._range_high = float("-inf")
        self._range_low = float("inf")
        self._range_set = False

    def get_default_params(self) -> dict:
        return {
            "orb_bars": 3,  # for daily data, use N bars instead of N minutes
            "stop_pct": 0.02,
            "target_pct": 0.04,
        }

    def get_param_grid(self) -> dict:
        return {
            "orb_bars": [2, 3, 5],
            "stop_pct": [0.015, 0.02, 0.03],
            "target_pct": [0.03, 0.04, 0.06],
        }

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        self._bar_count += 1
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        orb_bars = self.p["orb_bars"]

        # Build the opening range
        if self._bar_count <= orb_bars:
            self._range_high = max(self._range_high, high)
            self._range_low = min(self._range_low, low)
            if self._bar_count == orb_bars:
                self._range_set = True
            return None

        if not self._range_set:
            return None

        # Breakout above range high
        if close > self._range_high:
            return {"action": "buy", "price": close, "reason": f"ORB breakout above {self._range_high:.2f}"}

        # Breakdown below range low
        if close < self._range_low:
            return {"action": "sell", "price": close, "reason": f"ORB breakdown below {self._range_low:.2f}"}

        return None

    def reset(self):
        super().reset()
        self._bar_count = 0
        self._range_high = float("-inf")
        self._range_low = float("inf")
        self._range_set = False
