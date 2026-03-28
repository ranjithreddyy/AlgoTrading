from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class StrategyConfig:
    name: str
    family: str  # momentum, mean_reversion, options, etc.
    asset_class: str  # stock, option
    params: Dict[str, Any] = field(default_factory=dict)
    param_grid: Dict[str, List[Any]] = field(default_factory=dict)  # for parameter sweep


@dataclass
class BacktestResult:
    strategy_name: str
    params: Dict[str, Any]
    total_trades: int
    winning_trades: int
    losing_trades: int
    gross_pnl: float
    net_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    win_rate: float
    avg_trade_pnl: float
    equity_curve: List[float]
    trades: List[Dict]


class Strategy(ABC):
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.positions: List[Dict] = []
        self.trades: List[Dict] = []
        self.equity: List[float] = [0.0]

    @abstractmethod
    def on_bar(self, bar: dict, context: dict) -> Optional[dict]:
        """Process a new bar. Return signal dict or None.

        Signal dict format:
            {"action": "buy" | "sell", "price": float, "reason": str}
        """
        pass

    @abstractmethod
    def get_default_params(self) -> dict:
        pass

    @abstractmethod
    def get_param_grid(self) -> dict:
        """Return parameter grid for sweep."""
        pass

    def reset(self):
        self.positions = []
        self.trades = []
        self.equity = [0.0]
