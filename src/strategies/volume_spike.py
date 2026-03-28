"""Volume Spike Momentum Strategy.

Enter on volume spike with price confirmation (close > open for buy).
"""

from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy, StrategyConfig


class VolumeSpikeStrategy(Strategy):
    """Volume Spike Momentum - enter when volume spikes with price direction confirmation."""

    __strategy_name__ = "volume_spike"
    __default_family__ = "momentum"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._volumes: List[float] = []
        self._closes: List[float] = []

    def get_default_params(self) -> dict:
        return {
            "volume_multiplier": 2.0,
            "lookback": 20,
            "stop_pct": 0.02,
            "target_pct": 0.04,
        }

    def get_param_grid(self) -> dict:
        return {
            "volume_multiplier": [1.5, 2.0, 2.5],
            "lookback": [10, 20, 30],
            "stop_pct": [0.02, 0.03],
            "target_pct": [0.04, 0.06],
        }

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        open_ = bar["open"]
        volume = bar["volume"]

        self._volumes.append(volume)
        self._closes.append(close)

        lookback = self.p["lookback"]
        if len(self._volumes) < lookback + 1:
            return None

        avg_vol = sum(self._volumes[-lookback - 1: -1]) / lookback

        is_spike = volume >= avg_vol * self.p["volume_multiplier"]
        if not is_spike:
            return None

        bullish_bar = close > open_
        bearish_bar = close < open_

        # Also check that price is moving in a direction (close vs previous close)
        prev_close = self._closes[-2]

        if bullish_bar and close > prev_close:
            return {"action": "buy", "price": close, "reason": f"Volume spike ({volume/avg_vol:.1f}x) + bullish bar"}

        if bearish_bar and close < prev_close:
            return {"action": "sell", "price": close, "reason": f"Volume spike ({volume/avg_vol:.1f}x) + bearish bar"}

        return None

    def reset(self):
        super().reset()
        self._volumes = []
        self._closes = []
