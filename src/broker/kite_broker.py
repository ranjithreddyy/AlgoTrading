"""Kite Connect broker wrapper implementing the Broker interface."""

from typing import Any, Dict, List, Optional

from src.broker.base import Broker
from src.core.enums import OrderSide, OrderType, ProductType

# Mapping from our enums to Kite's string constants
_SIDE_MAP = {
    "BUY": "BUY",
    "SELL": "SELL",
    OrderSide.BUY: "BUY",
    OrderSide.SELL: "SELL",
}

_ORDER_TYPE_MAP = {
    "MARKET": "MARKET",
    "LIMIT": "LIMIT",
    "SL": "SL",
    "SL-M": "SL-M",
    "SLM": "SL-M",
    OrderType.MARKET: "MARKET",
    OrderType.LIMIT: "LIMIT",
    OrderType.SL: "SL",
    OrderType.SLM: "SL-M",
}

_PRODUCT_MAP = {
    "MIS": "MIS",
    "CNC": "CNC",
    "NRML": "NRML",
    ProductType.MIS: "MIS",
    ProductType.CNC: "CNC",
    ProductType.NRML: "NRML",
}


class KiteBroker(Broker):
    """Broker implementation wrapping KiteConnect API calls."""

    def __init__(
        self,
        kite_client: Any,
        exchange: str = "NSE",
        product: str = "MIS",
    ) -> None:
        """
        Args:
            kite_client: An authenticated ``KiteConnect`` instance.
            exchange: Default exchange (NSE, NFO, BSE, etc.).
            product: Default product type (MIS, CNC, NRML).
        """
        self.kite = kite_client
        self.exchange = exchange
        self.product = _PRODUCT_MAP.get(product, product)

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
    ) -> str:
        """Place an order via KiteConnect."""
        kite_side = _SIDE_MAP.get(side, side)
        kite_order_type = _ORDER_TYPE_MAP.get(order_type, order_type)

        params: Dict[str, Any] = {
            "tradingsymbol": symbol,
            "exchange": self.exchange,
            "transaction_type": kite_side,
            "quantity": quantity,
            "order_type": kite_order_type,
            "product": self.product,
            "variety": "regular",
        }

        if price is not None and kite_order_type in ("LIMIT", "SL"):
            params["price"] = price
        if price is not None and kite_order_type == "SL":
            params["trigger_price"] = price

        order_id = self.kite.place_order(**params)
        return str(order_id)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order via KiteConnect."""
        try:
            self.kite.cancel_order(variety="regular", order_id=order_id)
            return True
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Return order history for a given order ID."""
        try:
            history = self.kite.order_history(order_id=order_id)
            if history:
                return history[-1]  # latest state
            return {"order_id": order_id, "status": "UNKNOWN"}
        except Exception as exc:
            return {"order_id": order_id, "status": "ERROR", "error": str(exc)}

    def get_positions(self) -> List[Dict[str, Any]]:
        """Return current positions from Kite."""
        try:
            positions = self.kite.positions()
            # Kite returns {"net": [...], "day": [...]}
            return positions.get("net", [])
        except Exception:
            return []

    def get_orders(self) -> List[Dict[str, Any]]:
        """Return all orders for the day from Kite."""
        try:
            return self.kite.orders() or []
        except Exception:
            return []

    def get_balance(self) -> Dict[str, Any]:
        """Return margin / balance info from Kite."""
        try:
            margins = self.kite.margins()
            # margins is {"equity": {...}, "commodity": {...}}
            equity = margins.get("equity", {})
            return {
                "available_cash": equity.get("available", {}).get("cash", 0),
                "used_margin": equity.get("utilised", {}).get("debits", 0),
                "net": equity.get("net", 0),
            }
        except Exception as exc:
            return {"error": str(exc)}
