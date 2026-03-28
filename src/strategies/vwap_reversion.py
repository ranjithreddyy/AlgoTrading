"""VWAP Reversion Strategy.

Trade when price deviates significantly from VWAP then reverts back.
"""

from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy, StrategyConfig


class VWAPReversionStrategy(Strategy):
    """VWAP reversion - buy when price reverts towards VWAP after overshooting."""

    __strategy_name__ = "vwap_reversion"
    __default_family__ = "mean_reversion"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._cum_vol = 0.0
        self._cum_tp_vol = 0.0  # cumulative (typical_price * volume)
        self._prev_deviation = 0.0

    def get_default_params(self) -> dict:
        return {
            "deviation_threshold": 0.02,
            "stop_pct": 0.015,
            "target_pct": 0.03,
        }

    def get_param_grid(self) -> dict:
        return {
            "deviation_threshold": [0.015, 0.02, 0.025, 0.03],
            "stop_pct": [0.01, 0.015, 0.02],
            "target_pct": [0.02, 0.03, 0.04],
        }

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        high = bar["high"]
        low = bar["low"]
        close = bar["close"]
        volume = bar["volume"]

        typical_price = (high + low + close) / 3.0
        self._cum_vol += volume
        self._cum_tp_vol += typical_price * volume

        if self._cum_vol == 0:
            return None

        vwap = self._cum_tp_vol / self._cum_vol
        deviation = (close - vwap) / vwap if vwap != 0 else 0
        threshold = self.p["deviation_threshold"]

        signal = None

        # Price was significantly below VWAP and is now reverting up
        if self._prev_deviation < -threshold and deviation > self._prev_deviation and deviation > -threshold:
            signal = {"action": "buy", "price": close, "reason": f"VWAP reversion from below (dev: {deviation:.4f})"}

        # Price was significantly above VWAP and is now reverting down
        if self._prev_deviation > threshold and deviation < self._prev_deviation and deviation < threshold:
            signal = {"action": "sell", "price": close, "reason": f"VWAP reversion from above (dev: {deviation:.4f})"}

        self._prev_deviation = deviation
        return signal

    def reset(self):
        super().reset()
        self._cum_vol = 0.0
        self._cum_tp_vol = 0.0
        self._prev_deviation = 0.0
