"""Core data types used across the trading system."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from src.core.enums import OrderSide, Regime, TradeStatus


class Bar(BaseModel):
    """A single OHLCV bar."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    oi: Optional[int] = None


class Signal(BaseModel):
    """A trading signal emitted by a strategy."""

    timestamp: datetime
    symbol: str
    side: OrderSide
    strategy_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    regime: Regime = Regime.UNKNOWN
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Trade(BaseModel):
    """A completed or in-progress trade."""

    trade_id: str
    strategy_id: str
    symbol: str
    side: OrderSide
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    entry_time: datetime
    exit_time: Optional[datetime] = None
    pnl: float = 0.0
    slippage: float = 0.0
    status: TradeStatus = TradeStatus.PENDING


class Position(BaseModel):
    """A current position in a symbol."""

    symbol: str
    quantity: int
    avg_price: float
    pnl: float = 0.0
    side: OrderSide
