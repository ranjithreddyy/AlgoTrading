"""Kill switch for emergency trading halt."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class KillSwitch:
    """Global kill switch that halts all trading when activated."""

    def __init__(self) -> None:
        self._active: bool = False
        self._reason: str = ""
        self._log: List[Dict[str, Any]] = []

    def activate(self, reason: str) -> None:
        """Activate the kill switch, halting all trading."""
        self._active = True
        self._reason = reason
        self._log.append(
            {
                "action": "activate",
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def deactivate(self) -> None:
        """Deactivate the kill switch, resuming trading."""
        self._active = False
        self._log.append(
            {
                "action": "deactivate",
                "reason": "manual deactivation",
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def is_active(self) -> bool:
        """Return whether the kill switch is currently active."""
        return self._active

    @property
    def reason(self) -> str:
        """Return the reason for the current activation."""
        return self._reason

    @property
    def activation_log(self) -> List[Dict[str, Any]]:
        """Return the full log of activations / deactivations."""
        return list(self._log)

    def check_conditions(self, risk_manager: Any) -> None:
        """Auto-activate if risk limits are breached.

        Checks daily PnL, consecutive losses, and trade count against
        the risk manager's limits.
        """
        limits = risk_manager.limits

        if risk_manager.daily_pnl <= -abs(limits.max_daily_loss):
            self.activate(
                f"Daily loss limit breached: {risk_manager.daily_pnl:.2f}"
            )
            risk_manager.kill("kill_switch: daily loss limit")
            return

        if risk_manager.consecutive_losses >= limits.max_consecutive_losses:
            self.activate(
                f"Max consecutive losses reached: {risk_manager.consecutive_losses}"
            )
            risk_manager.kill("kill_switch: consecutive losses")
            return

        if risk_manager.trade_count >= limits.max_daily_trades:
            self.activate(
                f"Max daily trades reached: {risk_manager.trade_count}"
            )
            risk_manager.kill("kill_switch: daily trade limit")
            return

    def save_state(self, path: str) -> None:
        """Persist kill switch state to a JSON file."""
        state = {
            "active": self._active,
            "reason": self._reason,
            "log": self._log,
        }
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, indent=2))

    def load_state(self, path: str) -> None:
        """Load kill switch state from a JSON file."""
        p = Path(path)
        if not p.exists():
            return
        state = json.loads(p.read_text())
        self._active = state.get("active", False)
        self._reason = state.get("reason", "")
        self._log = state.get("log", [])
