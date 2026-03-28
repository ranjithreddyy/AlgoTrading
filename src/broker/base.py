"""Abstract broker interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class Broker(ABC):
    """Abstract base class for all broker implementations."""

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
    ) -> str:
        """Place an order and return an order ID."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Return True if successful."""
        ...

    @abstractmethod
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Return status dict for a given order ID."""
        ...

    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """Return list of current positions."""
        ...

    @abstractmethod
    def get_orders(self) -> List[Dict[str, Any]]:
        """Return list of all orders for the day."""
        ...

    @abstractmethod
    def get_balance(self) -> Dict[str, Any]:
        """Return account balance / margin information."""
        ...
