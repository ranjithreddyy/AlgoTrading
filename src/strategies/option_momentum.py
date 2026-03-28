"""Option Momentum Strategy - Buy CE on breakout, PE on breakdown using EMA crossover."""

from typing import List, Optional

from src.strategies.base import Strategy, StrategyConfig


class OptionMomentumStrategy(Strategy):
    """NIFTY Option Momentum: buy CE when NIFTY breaks above resistance with volume,
    buy PE on breakdown. Uses EMA crossover on the underlying as trend signal."""

    __strategy_name__ = "option_momentum"
    __default_family__ = "options"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._ema_fast: List[float] = []
        self._ema_slow: List[float] = []
        self._volumes: List[float] = []
        self._bar_count: int = 0
        self._in_position: bool = False
        self._entry_price: float = 0.0
        self._entry_bar: int = 0
        self._position_side: Optional[str] = None  # "long" or "short"

    def get_default_params(self) -> dict:
        return {
            "ema_fast": 9,
            "ema_slow": 21,
            "volume_threshold": 1.3,
            "stop_pct": 0.02,
            "target_pct": 0.04,
            "max_holding_bars": 20,
        }

    def get_param_grid(self) -> dict:
        return {
            "ema_fast": [5, 9, 12],
            "ema_slow": [15, 21, 30],
            "volume_threshold": [1.1, 1.3, 1.5],
            "stop_pct": [0.015, 0.02, 0.03],
            "target_pct": [0.03, 0.04, 0.06],
            "max_holding_bars": [10, 20, 30],
        }

    @staticmethod
    def _ema(prev: float, value: float, period: int) -> float:
        k = 2.0 / (period + 1)
        return value * k + prev * (1 - k)

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        volume = bar["volume"]
        self._bar_count += 1

        fast_p = self.p["ema_fast"]
        slow_p = self.p["ema_slow"]

        # Update EMAs
        if len(self._ema_fast) == 0:
            self._ema_fast.append(close)
            self._ema_slow.append(close)
        else:
            self._ema_fast.append(self._ema(self._ema_fast[-1], close, fast_p))
            self._ema_slow.append(self._ema(self._ema_slow[-1], close, slow_p))

        self._volumes.append(volume)

        # Need enough bars for slow EMA to stabilize
        if len(self._ema_fast) < slow_p + 1:
            return None

        cur_fast = self._ema_fast[-1]
        cur_slow = self._ema_slow[-1]
        prev_fast = self._ema_fast[-2]
        prev_slow = self._ema_slow[-2]

        # Average volume over lookback
        lookback = min(20, len(self._volumes) - 1)
        avg_vol = (
            sum(self._volumes[-lookback - 1 : -1]) / lookback
            if lookback > 0
            else volume
        )
        vol_ok = volume >= avg_vol * self.p["volume_threshold"]

        # If in position, check for exit signals
        if self._in_position:
            bars_held = self._bar_count - self._entry_bar
            # Max holding period exit
            if bars_held >= self.p["max_holding_bars"]:
                action = "sell" if self._position_side == "long" else "buy"
                reason = f"max holding bars reached ({self._position_side})"
                self._in_position = False
                self._position_side = None
                return {"action": action, "price": close, "reason": reason}

            # Exit long (CE) on bearish crossover
            if self._position_side == "long" and prev_fast >= prev_slow and cur_fast < cur_slow:
                self._in_position = False
                self._position_side = None
                return {"action": "sell", "price": close, "reason": "EMA bearish crossover - exit CE"}

            # Exit short (PE) on bullish crossover
            if self._position_side == "short" and prev_fast <= prev_slow and cur_fast > cur_slow:
                self._in_position = False
                self._position_side = None
                return {"action": "buy", "price": close, "reason": "EMA bullish crossover - exit PE"}

            return None

        # Entry signals (not in position)
        # Bullish crossover with volume -> Buy CE (go long)
        if prev_fast <= prev_slow and cur_fast > cur_slow and vol_ok:
            self._in_position = True
            self._entry_price = close
            self._entry_bar = self._bar_count
            self._position_side = "long"
            return {
                "action": "buy",
                "price": close,
                "reason": "EMA bullish crossover + volume -> buy CE",
                "side": "BUY",
                "option_type": "CE",
            }

        # Bearish crossover with volume -> Buy PE (go short)
        if prev_fast >= prev_slow and cur_fast < cur_slow and vol_ok:
            self._in_position = True
            self._entry_price = close
            self._entry_bar = self._bar_count
            self._position_side = "short"
            return {
                "action": "sell",
                "price": close,
                "reason": "EMA bearish crossover + volume -> buy PE",
                "side": "BUY",
                "option_type": "PE",
            }

        return None

    def reset(self):
        super().reset()
        self._ema_fast = []
        self._ema_slow = []
        self._volumes = []
        self._bar_count = 0
        self._in_position = False
        self._entry_price = 0.0
        self._entry_bar = 0
        self._position_side = None
