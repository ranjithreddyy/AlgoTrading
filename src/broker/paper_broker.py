"""Paper trading broker -- simulates order fills locally."""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.broker.base import Broker


class PaperBroker(Broker):
    """Simulated broker for paper trading and testing.

    Fills orders instantly at the requested price (plus configurable
    slippage) and tracks positions, balance, and PnL in memory.
    """

    def __init__(
        self,
        initial_capital: float = 500_000,
        slippage_pct: float = 0.001,
    ) -> None:
        self.initial_capital = initial_capital
        self.slippage_pct = slippage_pct

        self._cash: float = initial_capital
        self._positions: Dict[str, Dict[str, Any]] = {}  # symbol -> position
        self._orders: List[Dict[str, Any]] = []
        self._trade_log: List[Dict[str, Any]] = []
        self._order_counter: int = 0

    # ------------------------------------------------------------------
    # Broker interface
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
    ) -> str:
        """Place and immediately fill a simulated order."""
        self._order_counter += 1
        order_id = f"PAPER-{self._order_counter:06d}"
        side = side.upper()

        # Determine fill price with slippage
        if price is None:
            raise ValueError("Paper broker requires a price for order simulation")

        if side == "BUY":
            fill_price = price * (1 + self.slippage_pct)
        else:
            fill_price = price * (1 - self.slippage_pct)

        fill_price = round(fill_price, 2)
        notional = fill_price * quantity

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "requested_price": price,
            "fill_price": fill_price,
            "slippage": round(abs(fill_price - price) * quantity, 2),
            "status": "COMPLETE",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._orders.append(order)

        # Update positions and cash
        if side == "BUY":
            self._cash -= notional
            self._add_to_position(symbol, quantity, fill_price, "BUY")
        else:
            self._cash += notional
            self._add_to_position(symbol, -quantity, fill_price, "SELL")

        # Record in trade log
        self._trade_log.append(
            {
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": fill_price,
                "notional": round(notional, 2),
                "timestamp": order["timestamp"],
            }
        )

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        """Paper broker fills instantly, so cancellation always fails."""
        return False

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Return order details by ID."""
        for order in self._orders:
            if order["order_id"] == order_id:
                return order
        return {"order_id": order_id, "status": "NOT_FOUND"}

    def get_positions(self) -> List[Dict[str, Any]]:
        """Return list of open positions."""
        return [
            {**pos}
            for pos in self._positions.values()
            if pos["quantity"] != 0
        ]

    def get_orders(self) -> List[Dict[str, Any]]:
        """Return all orders."""
        return list(self._orders)

    def get_balance(self) -> Dict[str, Any]:
        """Return cash and portfolio value."""
        positions_value = sum(
            pos["avg_price"] * abs(pos["quantity"])
            for pos in self._positions.values()
        )
        return {
            "cash": round(self._cash, 2),
            "positions_value": round(positions_value, 2),
            "total_equity": round(self._cash + positions_value, 2),
            "initial_capital": self.initial_capital,
            "pnl": round(self._cash + positions_value - self.initial_capital, 2),
        }

    # ------------------------------------------------------------------
    # Paper-broker extras
    # ------------------------------------------------------------------

    def get_daily_report(self) -> Dict[str, Any]:
        """Generate a summary report for the day."""
        balance = self.get_balance()
        return {
            "total_orders": len(self._orders),
            "total_trades": len(self._trade_log),
            "open_positions": len(self.get_positions()),
            "cash": balance["cash"],
            "total_equity": balance["total_equity"],
            "pnl": balance["pnl"],
            "trade_log": self.get_trade_log(),
        }

    def get_trade_log(self) -> List[Dict[str, Any]]:
        """Return the full trade ledger."""
        return list(self._trade_log)

    def save_state(self, path: str) -> None:
        """Persist broker state to JSON for crash recovery."""
        state = {
            "initial_capital": self.initial_capital,
            "slippage_pct": self.slippage_pct,
            "cash": self._cash,
            "positions": self._positions,
            "orders": self._orders,
            "trade_log": self._trade_log,
            "order_counter": self._order_counter,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2))

    def load_state(self, path: str) -> None:
        """Load broker state from JSON."""
        p = Path(path)
        if not p.exists():
            return
        state = json.loads(p.read_text())
        self.initial_capital = state["initial_capital"]
        self.slippage_pct = state["slippage_pct"]
        self._cash = state["cash"]
        self._positions = state["positions"]
        self._orders = state["orders"]
        self._trade_log = state["trade_log"]
        self._order_counter = state["order_counter"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _add_to_position(
        self, symbol: str, signed_qty: int, fill_price: float, side: str
    ) -> None:
        """Update or create a position entry."""
        if symbol not in self._positions:
            self._positions[symbol] = {
                "symbol": symbol,
                "quantity": signed_qty,
                "avg_price": fill_price,
                "side": side,
                "pnl": 0.0,
            }
            return

        pos = self._positions[symbol]
        old_qty = pos["quantity"]
        new_qty = old_qty + signed_qty

        if new_qty == 0:
            # Position closed -- compute realized PnL
            if old_qty > 0:
                pnl = (fill_price - pos["avg_price"]) * abs(old_qty)
            else:
                pnl = (pos["avg_price"] - fill_price) * abs(old_qty)
            pos["pnl"] += round(pnl, 2)
            pos["quantity"] = 0
        elif (old_qty > 0 and new_qty > 0) or (old_qty < 0 and new_qty < 0):
            # Adding to position -- update avg price
            total_cost = pos["avg_price"] * abs(old_qty) + fill_price * abs(signed_qty)
            pos["avg_price"] = round(total_cost / abs(new_qty), 2)
            pos["quantity"] = new_qty
        else:
            # Flipped direction
            if old_qty > 0:
                pnl = (fill_price - pos["avg_price"]) * abs(old_qty)
            else:
                pnl = (pos["avg_price"] - fill_price) * abs(old_qty)
            pos["pnl"] += round(pnl, 2)
            pos["quantity"] = new_qty
            pos["avg_price"] = fill_price
            pos["side"] = side
