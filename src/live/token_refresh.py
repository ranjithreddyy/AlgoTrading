"""Token refresh automation for Kite Connect access tokens.

Kite Connect tokens expire at midnight IST daily.
This module handles validation, near-expiry detection,
and scheduled refresh coordination.
"""

import logging
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

# IST timezone (UTC+5:30)
_IST = timezone(timedelta(hours=5, minutes=30))

logger = logging.getLogger(__name__)


def _ist_now() -> datetime:
    """Return current datetime in IST."""
    return datetime.now(_IST)


class TokenRefreshManager:
    """Manage Kite Connect access token lifecycle.

    Tokens issued by Kite Connect expire at midnight IST each day.
    This manager can:
      - Validate whether the current token is still usable
      - Detect when the token is within a configurable warning window
      - Schedule an automatic refresh callback before market open
      - Persist a new token back to .env
    """

    EXPIRY_WARNING_HOURS: float = 2.0   # warn if < 2 h before midnight IST
    MARKET_OPEN_REFRESH_TIME = (8, 30)  # 8:30 AM IST – schedule refresh here

    def __init__(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
        warn_hours: float = EXPIRY_WARNING_HOURS,
    ) -> None:
        self.api_key = api_key or os.getenv("KITE_API_KEY", "")
        self.access_token = access_token or os.getenv("KITE_ACCESS_TOKEN", "")
        self.warn_hours = warn_hours
        self._scheduler_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Token validation
    # ------------------------------------------------------------------

    def check_token_valid(
        self,
        api_key: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> bool:
        """Check whether the given (or stored) token is valid.

        Attempts a lightweight Kite API call (profile).  If the call
        succeeds the token is valid.  If it fails (NetworkError,
        TokenException, etc.) the token is considered invalid.

        Returns:
            True if the token appears valid, False otherwise.
        """
        key = api_key or self.api_key
        token = access_token or self.access_token

        if not key or not token:
            logger.error(
                "Token validation failed: KITE_API_KEY or KITE_ACCESS_TOKEN is missing. "
                "Please run the auth flow and add the token to .env."
            )
            return False

        try:
            from kiteconnect import KiteConnect  # type: ignore

            kite = KiteConnect(api_key=key)
            kite.set_access_token(token)
            profile = kite.profile()
            user = profile.get("user_name", "unknown") if isinstance(profile, dict) else "ok"
            logger.info("Token valid – user: %s", user)
            return True
        except ImportError:
            logger.warning(
                "kiteconnect package not installed; cannot validate token online. "
                "Falling back to heuristic check."
            )
            # Heuristic: if a non-empty token exists we assume it might be valid
            return bool(token)
        except Exception as exc:
            logger.error(
                "Token invalid or expired: %s. "
                "Re-authenticate via the Kite login URL to get a new access token.",
                exc,
            )
            return False

    # ------------------------------------------------------------------
    # Expiry detection
    # ------------------------------------------------------------------

    def is_near_expiry(self) -> bool:
        """Return True if the token will expire within ``warn_hours`` hours.

        Kite tokens expire at 00:00 IST (midnight), so expiry is
        always the upcoming midnight in IST.
        """
        now_ist = _ist_now()
        # Midnight of the *next* day in IST
        tomorrow_midnight = (now_ist + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        hours_left = (tomorrow_midnight - now_ist).total_seconds() / 3600
        if hours_left < self.warn_hours:
            logger.warning(
                "Token is near expiry: %.1f hours until midnight IST. "
                "Re-authenticate before midnight to avoid trading interruptions.",
                hours_left,
            )
            return True
        return False

    def hours_until_expiry(self) -> float:
        """Return hours remaining until token expires at midnight IST."""
        now_ist = _ist_now()
        tomorrow_midnight = (now_ist + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return (tomorrow_midnight - now_ist).total_seconds() / 3600

    # ------------------------------------------------------------------
    # Auto-refresh
    # ------------------------------------------------------------------

    def auto_refresh_if_needed(self) -> bool:
        """Refresh the token if it is invalid or near expiry.

        For now, Kite Connect requires manual user interaction (browser
        login) to generate a new access token.  This method logs a clear
        error with instructions when a refresh is needed.

        Returns:
            True if the token is still valid (no refresh needed).
            False if refresh is required (user must re-authenticate).
        """
        if not self.check_token_valid():
            self._log_reauth_instructions()
            return False

        if self.is_near_expiry():
            hours = self.hours_until_expiry()
            logger.warning(
                "Token expires in %.1f h. Consider re-authenticating before midnight IST.",
                hours,
            )
            return True   # still valid – just a warning

        logger.info("Token is valid and not near expiry.")
        return True

    # ------------------------------------------------------------------
    # Scheduled refresh
    # ------------------------------------------------------------------

    def schedule_daily_refresh(self, callback: Callable[[], None]) -> None:
        """Schedule *callback* to run at 8:30 AM IST each day.

        The callback is responsible for initiating the re-authentication
        flow (e.g., opening the login URL or sending a Telegram reminder).

        Runs in a background daemon thread – safe to call from the main
        process without blocking.
        """
        def _scheduler_loop() -> None:
            logger.info("Token refresh scheduler started (fires at 08:30 IST daily).")
            while True:
                import time as _time

                now_ist = _ist_now()
                h, m = self.MARKET_OPEN_REFRESH_TIME
                target = now_ist.replace(hour=h, minute=m, second=0, microsecond=0)
                if now_ist >= target:
                    # Already past today's window; schedule for tomorrow
                    target += timedelta(days=1)

                sleep_seconds = (target - now_ist).total_seconds()
                logger.info(
                    "Next token refresh check in %.0f seconds (at %s IST).",
                    sleep_seconds,
                    target.strftime("%Y-%m-%d %H:%M"),
                )
                _time.sleep(sleep_seconds)

                logger.info("Running scheduled token refresh callback at 08:30 IST.")
                try:
                    callback()
                except Exception as exc:
                    logger.error("Scheduled token refresh callback failed: %s", exc)

        self._scheduler_thread = threading.Thread(
            target=_scheduler_loop, name="token-refresh-scheduler", daemon=True
        )
        self._scheduler_thread.start()

    # ------------------------------------------------------------------
    # Token persistence
    # ------------------------------------------------------------------

    def save_token(self, token: str, path: str = ".env") -> None:
        """Update KITE_ACCESS_TOKEN in the given .env file.

        If the key already exists it is updated in-place; otherwise it
        is appended.

        Args:
            token: The new access token string.
            path:  Path to the .env file (default: ``.env`` in cwd).
        """
        env_path = Path(path)
        if not env_path.is_absolute():
            # Resolve relative to repo root (two levels up from this file)
            repo_root = Path(__file__).resolve().parent.parent.parent
            env_path = repo_root / path

        existing = env_path.read_text() if env_path.exists() else ""
        pattern = re.compile(r"^KITE_ACCESS_TOKEN\s*=.*$", re.MULTILINE)

        if pattern.search(existing):
            new_content = pattern.sub(f"KITE_ACCESS_TOKEN={token}", existing)
        else:
            new_content = existing.rstrip("\n") + f"\nKITE_ACCESS_TOKEN={token}\n"

        env_path.write_text(new_content)
        self.access_token = token
        logger.info("Access token saved to %s", env_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_reauth_instructions(self) -> None:
        """Print a clear, actionable error message when re-auth is required."""
        api_key = self.api_key or "<your-api-key>"
        redirect = os.getenv("REDIRECTURL", "http://127.0.0.1:5000/")
        login_url = (
            f"https://kite.zerodha.com/connect/login"
            f"?api_key={api_key}&v=3"
        )
        logger.error(
            "\n"
            "======================================================\n"
            "  KITE ACCESS TOKEN IS INVALID OR EXPIRED\n"
            "======================================================\n"
            "  1. Open the following URL in your browser:\n"
            "     %s\n"
            "\n"
            "  2. Log in with your Zerodha credentials.\n"
            "\n"
            "  3. After login you will be redirected to:\n"
            "     %s?request_token=<TOKEN>\n"
            "     Copy the request_token from the URL.\n"
            "\n"
            "  4. Generate the access token:\n"
            "     python token_manager.py --request-token <TOKEN>\n"
            "\n"
            "  5. The new KITE_ACCESS_TOKEN will be saved in .env.\n"
            "======================================================",
            login_url,
            redirect,
        )

    def get_login_url(self) -> str:
        """Return the Kite login URL for manual re-authentication."""
        api_key = self.api_key or "<your-api-key>"
        return (
            f"https://kite.zerodha.com/connect/login"
            f"?api_key={api_key}&v=3"
        )
