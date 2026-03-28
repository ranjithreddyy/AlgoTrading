"""Alert system for trading notifications.

Supports multiple alert destinations: console (stderr), file, Telegram, and
generic webhooks.  An AlertRouter dispatches alerts to the appropriate
channels based on level.
"""

import json
import logging
import os
import sys
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Try to import requests; fall back gracefully if not installed.
try:
    import requests as _requests
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── Alert levels (ascending severity) ──────────────────────────────
INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"

_LEVEL_ORDER = {INFO: 0, WARNING: 1, ERROR: 2, CRITICAL: 3}

# Emoji prefixes for Telegram / rich-text output
_EMOJI = {
    INFO: "🟢",
    WARNING: "🟡",
    ERROR: "🔴",
    CRITICAL: "🚨",
}

# ANSI colours for console output
_COLORS = {
    INFO: "\033[94m",       # blue
    WARNING: "\033[93m",    # yellow
    ERROR: "\033[91m",      # red
    CRITICAL: "\033[95m",   # magenta
}
_RESET = "\033[0m"


# ── Abstract base ──────────────────────────────────────────────────
class AlertBackend(ABC):
    """Base class for alert delivery backends."""

    @abstractmethod
    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Send an alert.

        Args:
            level: One of INFO, WARNING, ERROR, CRITICAL.
            message: Human-readable alert text.
            data: Optional structured payload.
        """


# ── Console backend ───────────────────────────────────────────────
class ConsoleAlert(AlertBackend):
    """Print alerts to stderr with ANSI colour coding."""

    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        color = _COLORS.get(level, "")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{color}[{ts}] [{level}] {message}{_RESET}"
        if data:
            line += f"  {json.dumps(data)}"
        print(line, file=sys.stderr)


# ── File backend ──────────────────────────────────────────────────
class FileAlert(AlertBackend):
    """Append alerts to a log file with timestamps."""

    def __init__(self, log_path: Optional[str] = None) -> None:
        if log_path is None:
            repo_root = Path(__file__).resolve().parent.parent.parent
            log_path = str(repo_root / "artifacts" / "alerts" / "alerts.log")
        self.log_path = log_path
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)

    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"[{ts}] [{level}] {message}"
        if data:
            line += f"  {json.dumps(data)}"
        with open(self.log_path, "a") as fh:
            fh.write(line + "\n")


# ── Webhook backend ──────────────────────────────────────────────
class WebhookAlert(AlertBackend):
    """Post JSON payloads to a webhook URL (Slack, custom HTTP endpoints)."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
        }
        if data:
            payload["data"] = data

        if _requests is None:
            # Silently skip if requests is not installed
            return

        try:
            _requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
            )
        except Exception:
            # Best-effort: never let alert delivery crash the system
            pass


# ── Telegram backend ─────────────────────────────────────────────
class TelegramAlert(AlertBackend):
    """Send alerts to a Telegram chat via the Bot API.

    If ``bot_token`` or ``chat_id`` is absent the backend silently falls
    back to logging to a file so the rest of the system is unaffected.

    Message format::

        🟢 INFO | 2026-03-23T08:00:00Z
        Slippage spike detected
        {"avg": 0.05}

    Alert level emoji mapping:
        🟢 INFO  |  🟡 WARNING  |  🔴 ERROR  |  🚨 CRITICAL
    """

    _API_BASE = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        fallback_log_path: Optional[str] = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        self._enabled = bool(self.bot_token and self.chat_id)

        if not self._enabled:
            logger.info(
                "TelegramAlert: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set – "
                "falling back to file logging."
            )

        # Fallback file alert when Telegram is not configured
        self._fallback = FileAlert(log_path=fallback_log_path) if not self._enabled else None

    def _format_message(
        self, level: str, message: str, data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Build a nicely formatted Telegram message."""
        emoji = _EMOJI.get(level.upper(), "")
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [f"{emoji} *{level}* | `{ts}`", message]
        if data:
            lines.append(f"```\n{json.dumps(data, indent=2)}\n```")
        return "\n".join(lines)

    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Send a Telegram message; fall back to file if unconfigured."""
        if not self._enabled:
            if self._fallback:
                self._fallback.send(level, message, data)
            return

        if _requests is None:
            logger.warning("TelegramAlert: requests not installed; cannot send message.")
            return

        url = self._API_BASE.format(token=self.bot_token)
        text = self._format_message(level, message, data)

        try:
            resp = _requests.post(
                url,
                json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                timeout=5,
            )
            if not resp.ok:
                logger.warning(
                    "TelegramAlert: API returned %s – %s", resp.status_code, resp.text
                )
        except Exception as exc:
            # Best-effort delivery – never crash the trading system
            logger.warning("TelegramAlert: send failed: %s", exc)


# ── Router ────────────────────────────────────────────────────────
class AlertRouter:
    """Dispatch alerts to multiple backends based on severity level.

    WARNING and above go to *all* registered backends.
    INFO goes only to backends registered in the ``info_backends`` list
    (defaults to file-only).
    """

    def __init__(
        self,
        all_backends: Optional[List[AlertBackend]] = None,
        info_backends: Optional[List[AlertBackend]] = None,
    ) -> None:
        self.all_backends: List[AlertBackend] = all_backends or []
        self.info_backends: List[AlertBackend] = info_backends or []

    def send(self, level: str, message: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Route an alert to the appropriate backends."""
        level = level.upper()
        if _LEVEL_ORDER.get(level, 0) >= _LEVEL_ORDER[WARNING]:
            for backend in self.all_backends:
                backend.send(level, message, data)
        else:
            for backend in self.info_backends:
                backend.send(level, message, data)


# ── Convenience manager ──────────────────────────────────────────
class AlertManager:
    """High-level alert manager with optional Telegram/webhook support.

    Usage::

        mgr = AlertManager(webhook_url="https://hooks.slack.com/xxx")
        mgr.send_alert("WARNING", "Slippage spike", {"avg": 0.05})
    """

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        telegram_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        log_path: Optional[str] = None,
    ) -> None:
        self.console = ConsoleAlert()
        self.file = FileAlert(log_path=log_path)

        all_backends: List[AlertBackend] = [self.console, self.file]
        info_backends: List[AlertBackend] = [self.file]

        if webhook_url:
            wb = WebhookAlert(webhook_url)
            all_backends.append(wb)

        if telegram_token and telegram_chat_id:
            all_backends.append(
                TelegramAlert(bot_token=telegram_token, chat_id=telegram_chat_id)
            )
        elif os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            # Auto-pick up from env if explicit args not provided
            all_backends.append(TelegramAlert())

        self.router = AlertRouter(
            all_backends=all_backends,
            info_backends=info_backends,
        )

    def send_alert(
        self,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send an alert via all configured channels."""
        self.router.send(level, message, data)
