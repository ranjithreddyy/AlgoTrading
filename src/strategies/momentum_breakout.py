"""Momentum Breakout Strategy - EMA crossover with volume confirmation."""

from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy, StrategyConfig


class MomentumBreakoutStrategy(Strategy):
    """EMA crossover strategy confirmed by above-average volume."""

    __strategy_name__ = "momentum_breakout"
    __default_family__ = "momentum"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._ema_fast: List[float] = []
        self._ema_slow: List[float] = []
        self._volumes: List[float] = []

    def get_default_params(self) -> dict:
        return {
            "fast_period": 9,
            "slow_period": 21,
            "volume_multiplier": 1.2,
            "stop_pct": 0.02,
            "target_pct": 0.04,
        }

    def get_param_grid(self) -> dict:
        return {
            "fast_period": [5, 9, 12],
            "slow_period": [15, 21, 30],
            "volume_multiplier": [1.0, 1.2, 1.5],
            "stop_pct": [0.02, 0.03],
            "target_pct": [0.04, 0.06],
        }

    @staticmethod
    def _ema(prev: float, value: float, period: int) -> float:
        k = 2.0 / (period + 1)
        return value * k + prev * (1 - k)

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        volume = bar["volume"]
        fast_p = self.p["fast_period"]
        slow_p = self.p["slow_period"]

        # Update EMAs
        if len(self._ema_fast) == 0:
            self._ema_fast.append(close)
            self._ema_slow.append(close)
        else:
            self._ema_fast.append(self._ema(self._ema_fast[-1], close, fast_p))
            self._ema_slow.append(self._ema(self._ema_slow[-1], close, slow_p))

        self._volumes.append(volume)

        # Need at least slow_period bars
        if len(self._ema_fast) < slow_p + 1:
            return None

        cur_fast = self._ema_fast[-1]
        cur_slow = self._ema_slow[-1]
        prev_fast = self._ema_fast[-2]
        prev_slow = self._ema_slow[-2]

        # Average volume over lookback
        lookback = min(20, len(self._volumes) - 1)
        avg_vol = sum(self._volumes[-lookback - 1 : -1]) / lookback if lookback > 0 else volume

        vol_ok = volume >= avg_vol * self.p["volume_multiplier"]

        # Bullish crossover
        if prev_fast <= prev_slow and cur_fast > cur_slow and vol_ok:
            return {"action": "buy", "price": close, "reason": "EMA bullish crossover + volume"}

        # Bearish crossover (exit signal)
        if prev_fast >= prev_slow and cur_fast < cur_slow:
            return {"action": "sell", "price": close, "reason": "EMA bearish crossover"}

        return None

    def reset(self):
        super().reset()
        self._ema_fast = []
        self._ema_slow = []
        self._volumes = []
