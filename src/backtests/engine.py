"""Simple backtest engine with cost model."""

import math
from typing import Dict, List, Optional

import pandas as pd

from src.backtests.costs import IndianCostModel
from src.strategies.base import BacktestResult, Strategy, StrategyConfig


# Legacy cost model constants (kept for backward compatibility)
BROKERAGE_PCT = 0.0003   # 0.03%
SLIPPAGE_PCT = 0.0001    # 0.01%
TOTAL_COST_PCT = BROKERAGE_PCT + SLIPPAGE_PCT  # applied per side


class BacktestEngine:
    """Run a strategy on historical bar data and produce a BacktestResult."""

    def __init__(
        self,
        cost_model: Optional[IndianCostModel] = None,
        instrument_type: str = "EQ",
        slippage_pct: float = SLIPPAGE_PCT,
    ):
        """Initialise the engine.

        Args:
            cost_model: An IndianCostModel instance.  When *None* (default),
                a new ``IndianCostModel()`` is created automatically.
            instrument_type: 'EQ', 'EQ_DEL', or 'OPT' – passed through to
                the cost model.
            slippage_pct: Additional slippage percentage applied per side on
                top of the cost-model fees.
        """
        self.cost_model = cost_model or IndianCostModel()
        self.instrument_type = instrument_type
        self.slippage_pct = slippage_pct

    def run(self, strategy: Strategy, data_df: pd.DataFrame) -> BacktestResult:
        """Run backtest.

        Args:
            strategy: An instantiated Strategy object.
            data_df: DataFrame with columns: date, open, high, low, close, volume.
                     'date' can be the index or a column.

        Returns:
            BacktestResult with performance metrics.
        """
        strategy.reset()
        params = strategy.config.params

        stop_pct = params.get("stop_pct", 0.02)
        target_pct = params.get("target_pct", 0.04)

        trades: List[Dict] = []
        equity_curve: List[float] = [0.0]
        position = None  # {"side": "long"/"short", "entry": float, "entry_date": str}

        df = data_df.reset_index() if "date" not in data_df.columns else data_df.copy()

        for idx, row in df.iterrows():
            bar = {
                "date": str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            }
            context = {"position": position}

            # Check stop/target if in position
            if position is not None:
                exit_signal = self._check_exit(position, bar, stop_pct, target_pct)
                if exit_signal:
                    pnl = self._close_position(position, exit_signal["price"], bar["date"])
                    trades.append(pnl)
                    equity_curve.append(equity_curve[-1] + pnl["net_pnl"])
                    position = None
                    continue

            signal = strategy.on_bar(bar, context)

            if signal is None:
                equity_curve.append(equity_curve[-1])
                continue

            action = signal["action"]
            price = signal["price"]

            if position is None:
                # Open new position
                if action == "buy":
                    position = {"side": "long", "entry": price, "entry_date": bar["date"]}
                elif action == "sell":
                    position = {"side": "short", "entry": price, "entry_date": bar["date"]}
                equity_curve.append(equity_curve[-1])
            else:
                # Close existing position if signal is opposite
                should_close = (
                    (position["side"] == "long" and action == "sell")
                    or (position["side"] == "short" and action == "buy")
                )
                if should_close:
                    pnl = self._close_position(position, price, bar["date"])
                    trades.append(pnl)
                    equity_curve.append(equity_curve[-1] + pnl["net_pnl"])
                    position = None
                else:
                    equity_curve.append(equity_curve[-1])

        # Force close any open position at last bar
        if position is not None:
            last_row = df.iloc[-1]
            pnl = self._close_position(position, float(last_row["close"]), str(last_row["date"]))
            trades.append(pnl)
            equity_curve.append(equity_curve[-1] + pnl["net_pnl"])

        return self._build_result(strategy.config.name, params, trades, equity_curve)

    @staticmethod
    def _check_exit(position: dict, bar: dict, stop_pct: float, target_pct: float):
        """Check if stop loss or target is hit on this bar."""
        entry = position["entry"]
        if position["side"] == "long":
            stop_price = entry * (1 - stop_pct)
            target_price = entry * (1 + target_pct)
            if bar["low"] <= stop_price:
                return {"price": stop_price, "reason": "stop_loss"}
            if bar["high"] >= target_price:
                return {"price": target_price, "reason": "target"}
        else:  # short
            stop_price = entry * (1 + stop_pct)
            target_price = entry * (1 - target_pct)
            if bar["high"] >= stop_price:
                return {"price": stop_price, "reason": "stop_loss"}
            if bar["low"] <= target_price:
                return {"price": target_price, "reason": "target"}
        return None

    def _close_position(self, position: dict, exit_price: float, exit_date: str) -> dict:
        entry = position["entry"]
        side = position["side"]

        if side == "long":
            gross_pnl = exit_price - entry
        else:
            gross_pnl = entry - exit_price

        # Use IndianCostModel for realistic cost calculation
        rt = self.cost_model.total_round_trip_cost(
            entry, exit_price, 1, self.instrument_type
        )
        model_cost = rt["total"]

        # Add slippage on both legs
        slippage = entry * self.slippage_pct + exit_price * self.slippage_pct
        cost = model_cost + slippage
        net_pnl = gross_pnl - cost

        return {
            "side": side,
            "entry_price": entry,
            "exit_price": exit_price,
            "entry_date": position["entry_date"],
            "exit_date": exit_date,
            "gross_pnl": gross_pnl,
            "cost": cost,
            "net_pnl": net_pnl,
        }

    @staticmethod
    def _build_result(
        strategy_name: str,
        params: dict,
        trades: List[Dict],
        equity_curve: List[float],
    ) -> BacktestResult:
        total_trades = len(trades)
        if total_trades == 0:
            return BacktestResult(
                strategy_name=strategy_name,
                params=params,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                gross_pnl=0.0,
                net_pnl=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                profit_factor=0.0,
                win_rate=0.0,
                avg_trade_pnl=0.0,
                equity_curve=equity_curve,
                trades=trades,
            )

        winners = [t for t in trades if t["net_pnl"] > 0]
        losers = [t for t in trades if t["net_pnl"] <= 0]
        gross_pnl = sum(t["gross_pnl"] for t in trades)
        net_pnl = sum(t["net_pnl"] for t in trades)

        # Max drawdown
        peak = equity_curve[0]
        max_dd = 0.0
        for v in equity_curve:
            if v > peak:
                peak = v
            dd = peak - v
            if dd > max_dd:
                max_dd = dd

        # Sharpe ratio (daily returns proxy)
        returns = []
        for i in range(1, len(equity_curve)):
            returns.append(equity_curve[i] - equity_curve[i - 1])
        if returns:
            mean_ret = sum(returns) / len(returns)
            var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
            std_ret = math.sqrt(var) if var > 0 else 1e-9
            sharpe = (mean_ret / std_ret) * math.sqrt(252) if std_ret > 1e-9 else 0.0
        else:
            sharpe = 0.0

        # Profit factor
        gross_wins = sum(t["net_pnl"] for t in winners)
        gross_losses = abs(sum(t["net_pnl"] for t in losers))
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float("inf") if gross_wins > 0 else 0.0

        win_rate = len(winners) / total_trades if total_trades > 0 else 0.0
        avg_trade_pnl = net_pnl / total_trades

        return BacktestResult(
            strategy_name=strategy_name,
            params=params,
            total_trades=total_trades,
            winning_trades=len(winners),
            losing_trades=len(losers),
            gross_pnl=round(gross_pnl, 2),
            net_pnl=round(net_pnl, 2),
            max_drawdown=round(max_dd, 2),
            sharpe_ratio=round(sharpe, 4),
            profit_factor=round(profit_factor, 4),
            win_rate=round(win_rate, 4),
            avg_trade_pnl=round(avg_trade_pnl, 2),
            equity_curve=equity_curve,
            trades=trades,
        )
