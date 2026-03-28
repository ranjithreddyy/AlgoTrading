"""Mean Reversion Strategy - RSI-based."""

from typing import Any, Dict, List, Optional

from src.strategies.base import Strategy, StrategyConfig


class MeanReversionStrategy(Strategy):
    """RSI-based mean reversion: buy oversold, sell overbought."""

    __strategy_name__ = "mean_reversion"
    __default_family__ = "mean_reversion"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._closes: List[float] = []
        self._rsi_values: List[float] = []

    def get_default_params(self) -> dict:
        return {
            "rsi_period": 14,
            "oversold": 30,
            "overbought": 70,
            "stop_pct": 0.02,
            "target_pct": 0.04,
        }

    def get_param_grid(self) -> dict:
        return {
            "rsi_period": [7, 14, 21],
            "oversold": [25, 30, 35],
            "overbought": [65, 70, 75],
            "stop_pct": [0.02, 0.03],
            "target_pct": [0.04, 0.06],
        }

    def _compute_rsi(self) -> Optional[float]:
        period = self.p["rsi_period"]
        if len(self._closes) < period + 1:
            return None

        gains = []
        losses = []
        for i in range(-period, 0):
            delta = self._closes[i] - self._closes[i - 1]
            if delta > 0:
                gains.append(delta)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(delta))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        self._closes.append(close)

        rsi = self._compute_rsi()
        if rsi is None:
            return None

        self._rsi_values.append(rsi)

        # Buy when RSI crosses up through oversold
        if len(self._rsi_values) >= 2:
            prev_rsi = self._rsi_values[-2]

            if prev_rsi <= self.p["oversold"] and rsi > self.p["oversold"]:
                return {"action": "buy", "price": close, "reason": f"RSI crossed above oversold ({rsi:.1f})"}

            if prev_rsi >= self.p["overbought"] and rsi < self.p["overbought"]:
                return {"action": "sell", "price": close, "reason": f"RSI crossed below overbought ({rsi:.1f})"}

        return None

    def reset(self):
        super().reset()
        self._closes = []
        self._rsi_values = []
