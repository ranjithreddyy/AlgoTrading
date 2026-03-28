"""Crash recovery -- state persistence and reconciliation."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateManager:
    """Manages persistence and reconciliation of trading state."""

    def __init__(self, auto_save_path: Optional[str] = None) -> None:
        """
        Args:
            auto_save_path: If set, state is automatically persisted to
                this path on every call to save_state.
        """
        self._auto_save_path = auto_save_path
        self._last_state: Optional[Dict[str, Any]] = None

    def save_state(
        self,
        positions: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
        pnl: float,
        path: Optional[str] = None,
    ) -> None:
        """Save current trading state to JSON.

        Args:
            positions: List of open position dicts.
            orders: List of order dicts.
            pnl: Current PnL value.
            path: File path to write. Falls back to auto_save_path.
        """
        target = path or self._auto_save_path
        if target is None:
            raise ValueError("No path provided and no auto_save_path configured")

        state = {
            "timestamp": datetime.utcnow().isoformat(),
            "positions": positions,
            "orders": orders,
            "pnl": pnl,
        }
        self._last_state = state

        p = Path(target)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2))

    def load_state(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Load trading state from JSON.

        Args:
            path: File path to read. Falls back to auto_save_path.

        Returns:
            State dict with keys: timestamp, positions, orders, pnl.
            Returns empty dict if file does not exist.
        """
        target = path or self._auto_save_path
        if target is None:
            raise ValueError("No path provided and no auto_save_path configured")

        p = Path(target)
        if not p.exists():
            return {}

        state = json.loads(p.read_text())
        self._last_state = state
        return state

    @staticmethod
    def reconcile(
        local_state: Dict[str, Any],
        broker_positions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Compare local state with broker positions and find discrepancies.

        Args:
            local_state: State dict as returned by load_state (must have
                'positions' key).
            broker_positions: List of position dicts from the broker
                (each must have 'symbol' and 'quantity' keys).

        Returns:
            List of discrepancy dicts, each with keys: symbol, local_qty,
            broker_qty, type ('missing_local', 'missing_broker', 'qty_mismatch').
        """
        discrepancies: List[Dict[str, Any]] = []

        local_positions = local_state.get("positions", [])
        local_map: Dict[str, int] = {
            p["symbol"]: p.get("quantity", 0) for p in local_positions
        }
        broker_map: Dict[str, int] = {
            p["symbol"]: p.get("quantity", 0) for p in broker_positions
        }

        all_symbols = set(local_map.keys()) | set(broker_map.keys())

        for symbol in sorted(all_symbols):
            local_qty = local_map.get(symbol, 0)
            broker_qty = broker_map.get(symbol, 0)

            if local_qty == broker_qty:
                continue

            if symbol not in local_map:
                disc_type = "missing_local"
            elif symbol not in broker_map:
                disc_type = "missing_broker"
            else:
                disc_type = "qty_mismatch"

            discrepancies.append(
                {
                    "symbol": symbol,
                    "local_qty": local_qty,
                    "broker_qty": broker_qty,
                    "type": disc_type,
                }
            )

        return discrepancies
