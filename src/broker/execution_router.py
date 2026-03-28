"""Execution router -- checks risk limits then routes to broker."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.broker.base import Broker
from src.risk.kill_switch import KillSwitch
from src.risk.limits import RiskManager

logger = logging.getLogger(__name__)


class ExecutionRouter:
    """Routes order signals through risk checks to the configured broker."""

    def __init__(
        self,
        broker: Broker,
        risk_manager: RiskManager,
        kill_switch: KillSwitch,
    ) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self.kill_switch = kill_switch
        self._submission_log: List[Dict[str, Any]] = []

    def submit_signal(
        self,
        signal: Dict[str, Any],
        current_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Submit a trading signal for execution.

        Args:
            signal: Dict with keys: symbol, side, quantity, order_type,
                and optionally price, notional, timestamp.
            current_state: Optional dict passed to risk manager's
                check_trade (open_positions, notional_exposure, capital,
                market_open_time, market_close_time, now).

        Returns:
            Dict with 'status' ('filled', 'rejected'), 'order_id' (if
            filled), and 'reason' (if rejected).
        """
        current_state = current_state or {}
        timestamp = datetime.utcnow().isoformat()

        # 1. Kill switch check
        if self.kill_switch.is_active():
            result = {
                "status": "rejected",
                "reason": f"Kill switch active: {self.kill_switch.reason}",
                "timestamp": timestamp,
            }
            self._log_submission(signal, result)
            return result

        # 2. Risk limit check
        allowed, reason = self.risk_manager.check_trade(signal, current_state)
        if not allowed:
            result = {
                "status": "rejected",
                "reason": reason,
                "timestamp": timestamp,
            }
            self._log_submission(signal, result)
            return result

        # 3. Route to broker
        try:
            order_id = self.broker.place_order(
                symbol=signal["symbol"],
                side=signal["side"],
                quantity=signal["quantity"],
                order_type=signal.get("order_type", "MARKET"),
                price=signal.get("price"),
            )
            result = {
                "status": "filled",
                "order_id": order_id,
                "timestamp": timestamp,
            }
        except Exception as exc:
            logger.error("Order placement failed: %s", exc)
            result = {
                "status": "error",
                "reason": str(exc),
                "timestamp": timestamp,
            }

        self._log_submission(signal, result)

        # Auto-check kill switch conditions after every submission
        self.kill_switch.check_conditions(self.risk_manager)

        return result

    @property
    def submission_log(self) -> List[Dict[str, Any]]:
        """Return full log of submissions and outcomes."""
        return list(self._submission_log)

    def _log_submission(
        self, signal: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        entry = {
            "signal": signal,
            "result": result,
        }
        self._submission_log.append(entry)
        logger.info("Submission: %s -> %s", signal.get("symbol", "?"), result["status"])
