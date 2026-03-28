"""Straddle Breakout Strategy - Long premium when volatility expansion is expected."""

import math
from typing import List, Optional

from src.strategies.base import Strategy, StrategyConfig


class StraddleBreakoutStrategy(Strategy):
    """Straddle Breakout (long premium): simulates buying both CE and PE when a big
    move is expected. Enters when volatility is compressed (low ATR percentile) and
    volume surges, expecting volatility expansion. The bar data represents the
    underlying; the strategy simulates option P&L via directional moves."""

    __strategy_name__ = "straddle_breakout"
    __default_family__ = "options"

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self.p = {**self.get_default_params(), **config.params}
        self._highs: List[float] = []
        self._lows: List[float] = []
        self._closes: List[float] = []
        self._volumes: List[float] = []
        self._atrs: List[float] = []
        self._in_position: bool = False
        self._entry_price: float = 0.0
        self._entry_bar: int = 0
        self._bar_count: int = 0

    def get_default_params(self) -> dict:
        return {
            "atr_period": 14,
            "atr_low_percentile": 25,
            "volume_spike_mult": 1.5,
            "stop_pct": 0.015,
            "target_pct": 0.03,
        }

    def get_param_grid(self) -> dict:
        return {
            "atr_period": [10, 14, 20],
            "atr_low_percentile": [15, 25, 35],
            "volume_spike_mult": [1.3, 1.5, 2.0],
            "stop_pct": [0.01, 0.015, 0.02],
            "target_pct": [0.025, 0.03, 0.04],
        }

    def _compute_atr(self) -> Optional[float]:
        """Compute current ATR from stored highs, lows, closes."""
        period = self.p["atr_period"]
        if len(self._closes) < period + 1:
            return None
        trs = []
        for i in range(-period, 0):
            h = self._highs[i]
            l = self._lows[i]
            prev_c = self._closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
        return sum(trs) / period

    def _atr_percentile_rank(self, current_atr: float) -> float:
        """Percentile rank of current ATR among recent ATR values."""
        if len(self._atrs) < 2:
            return 50.0
        lookback = min(100, len(self._atrs))
        recent = self._atrs[-lookback:]
        count_below = sum(1 for a in recent if a <= current_atr)
        return (count_below / len(recent)) * 100.0

    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        close = bar["close"]
        high = bar["high"]
        low = bar["low"]
        volume = bar["volume"]
        self._bar_count += 1

        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        self._volumes.append(volume)

        atr = self._compute_atr()
        if atr is None:
            return None
        self._atrs.append(atr)

        atr_pct_rank = self._atr_percentile_rank(atr)

        # Average volume
        lookback = min(20, len(self._volumes) - 1)
        avg_vol = (
            sum(self._volumes[-lookback - 1 : -1]) / lookback
            if lookback > 0
            else volume
        )
        vol_spike = volume >= avg_vol * self.p["volume_spike_mult"]

        # If in position, look for big directional move to exit (simulating straddle profit)
        if self._in_position:
            move_pct = abs(close - self._entry_price) / self._entry_price
            # Straddle profits from large moves in either direction
            # Exit with profit when the move exceeds target
            if move_pct >= self.p["target_pct"]:
                # Determine direction for engine compatibility
                if close > self._entry_price:
                    action = "sell"
                    reason = f"straddle profit: underlying moved +{move_pct:.1%}"
                else:
                    action = "buy"
                    reason = f"straddle profit: underlying moved -{move_pct:.1%}"
                self._in_position = False
                return {"action": action, "price": close, "reason": reason}

            # Time-based exit after too many bars without movement
            bars_held = self._bar_count - self._entry_bar
            if bars_held >= 15:
                self._in_position = False
                # Close as a loss (theta decay simulation)
                if close >= self._entry_price:
                    return {"action": "sell", "price": close, "reason": "straddle theta decay - time exit"}
                else:
                    return {"action": "buy", "price": close, "reason": "straddle theta decay - time exit"}

            return None

        # Entry: Low ATR percentile (compressed volatility) + volume surge
        if atr_pct_rank <= self.p["atr_low_percentile"] and vol_spike:
            self._in_position = True
            self._entry_price = close
            self._entry_bar = self._bar_count
            # Enter long for engine compatibility; the strategy simulates straddle
            return {
                "action": "buy",
                "price": close,
                "reason": f"volatility compressed (ATR pctile={atr_pct_rank:.0f}) + volume spike -> straddle entry",
                "side": "BUY",
                "option_type": "CE+PE",
            }

        return None

    def reset(self):
        super().reset()
        self._highs = []
        self._lows = []
        self._closes = []
        self._volumes = []
        self._atrs = []
        self._in_position = False
        self._entry_price = 0.0
        self._entry_bar = 0
        self._bar_count = 0
