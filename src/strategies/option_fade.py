"""Option Fade Strategy - Mean reversion on NIFTY using RSI + Bollinger Bands."""

from typing import List, Optional

from src.strategies.base import Strategy, StrategyConfig


class OptionFadeStrategy(Strategy):
    """NIFTY Option Range Fade: buy PE at resistance (overbought), buy CE at support
    (oversold). Uses RSI + Bollinger Bands to detect overbought/oversold conditions.
    Tighter stops and quicker targets than momentum strategies."""

    __strategy_name__ = "option_fade"
    __default_family__ = "options"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._closes: List[float] = []
        self._in_position: bool = False
        self._entry_price: float = 0.0
        self._position_side: Optional[str] = None  # "long" or "short"

    def get_default_params(self) -> dict:
        return {
            "rsi_period": 14,
            "rsi_upper": 70,
            "rsi_lower": 30,
            "bb_period": 20,
            "bb_std": 2.0,
            "stop_pct": 0.015,
            "target_pct": 0.025,
        }

    def get_param_grid(self) -> dict:
        return {
            "rsi_period": [10, 14],
            "rsi_upper": [65, 70, 75],
            "rsi_lower": [25, 30, 35],
            "bb_period": [15, 20],
            "bb_std": [1.5, 2.0, 2.5],
            "stop_pct": [0.01, 0.015, 0.02],
            "target_pct": [0.02, 0.025, 0.03],
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

    @staticmethod
    def _compute_bb(closes: List[float], period: int, num_std: float):
        """Compute Bollinger Band upper, middle, lower from last `period` closes."""
        if len(closes) < period:
            return None, None, None
        window = closes[-period:]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        return mean + num_std * std, mean, mean - num_std * std

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        self._closes.append(close)

        rsi_period = self.p["rsi_period"]
        bb_period = self.p["bb_period"]
        min_bars = max(rsi_period + 1, bb_period)

        if len(self._closes) < min_bars:
            return None

        rsi = self._compute_rsi(self._closes, rsi_period)
        bb_upper, bb_mid, bb_lower = self._compute_bb(
            self._closes, bb_period, self.p["bb_std"]
        )

        if rsi is None or bb_upper is None:
            return None

        # If in position, check for mean-reversion exit
        if self._in_position:
            # Long (bought CE at support) -> exit when price reverts to middle band
            if self._position_side == "long" and close >= bb_mid:
                self._in_position = False
                self._position_side = None
                return {"action": "sell", "price": close, "reason": "price reverted to BB mid - exit CE"}

            # Short (bought PE at resistance) -> exit when price reverts to middle band
            if self._position_side == "short" and close <= bb_mid:
                self._in_position = False
                self._position_side = None
                return {"action": "buy", "price": close, "reason": "price reverted to BB mid - exit PE"}

            return None

        # Entry: Oversold at support -> buy CE (go long, expecting bounce)
        if rsi <= self.p["rsi_lower"] and close <= bb_lower:
            self._in_position = True
            self._entry_price = close
            self._position_side = "long"
            return {
                "action": "buy",
                "price": close,
                "reason": f"RSI={rsi:.1f} oversold + below BB lower -> buy CE",
                "side": "BUY",
                "option_type": "CE",
            }

        # Entry: Overbought at resistance -> buy PE (go short, expecting pullback)
        if rsi >= self.p["rsi_upper"] and close >= bb_upper:
            self._in_position = True
            self._entry_price = close
            self._position_side = "short"
            return {
                "action": "sell",
                "price": close,
                "reason": f"RSI={rsi:.1f} overbought + above BB upper -> buy PE",
                "side": "BUY",
                "option_type": "PE",
            }

        return None

    def reset(self):
        super().reset()
        self._closes = []
        self._in_position = False
        self._entry_price = 0.0
        self._position_side = None
