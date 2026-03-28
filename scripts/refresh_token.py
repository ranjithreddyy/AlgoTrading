#!/usr/bin/env python
"""refresh_token.py – Check and manage Kite Connect access token.

Usage:
    python scripts/refresh_token.py          # Check token status
    python scripts/refresh_token.py --auto   # Schedule daily refresh at 08:30 IST

Exit codes:
    0 – token is valid
    1 – token is invalid / expired (user action required)
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Kite Connect token manager")
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Schedule a daily refresh callback at 08:30 IST (runs in foreground until Ctrl-C)",
    )
    args = parser.parse_args()

    # Load settings (this also loads .env via load_dotenv)
    from src.config.settings import KITE_API_KEY, KITE_ACCESS_TOKEN, REPO_ROOT as ROOT
    from src.live.token_refresh import TokenRefreshManager

    mgr = TokenRefreshManager(api_key=KITE_API_KEY, access_token=KITE_ACCESS_TOKEN)

    print()
    print("=" * 54)
    print("  KITE ACCESS TOKEN STATUS")
    print("=" * 54)

    # --- Validity check ---
    is_valid = mgr.check_token_valid()
    status_str = "VALID" if is_valid else "INVALID / EXPIRED"
    print(f"  Token status  : {status_str}")

    # --- Expiry info ---
    hours_left = mgr.hours_until_expiry()
    near = mgr.is_near_expiry()
    print(f"  Expires in    : {hours_left:.1f} hours (midnight IST)")
    if near:
        print("  WARNING       : Token is within the 2-hour expiry warning window!")

    print("=" * 54)

    if not is_valid:
        print()
        print("  ACTION REQUIRED:")
        login_url = mgr.get_login_url()
        print(f"  1. Open: {login_url}")
        print("  2. Log in with your Zerodha credentials.")
        print("  3. Copy the request_token from the redirect URL.")
        print("  4. Run: python token_manager.py --request-token <TOKEN>")
        print()
        return 1

    # --- Scheduling ---
    if args.auto:
        print()
        print("  --auto flag set: scheduling daily refresh at 08:30 IST.")
        print("  Press Ctrl-C to stop.")
        print()

        def _refresh_callback() -> None:
            logger.info("Scheduled refresh callback fired.")
            ok = mgr.check_token_valid()
            if not ok:
                logger.error("Token invalid at scheduled check – please re-authenticate.")
                logger.error("Login URL: %s", mgr.get_login_url())
            else:
                logger.info("Token still valid – no action needed.")

        mgr.schedule_daily_refresh(_refresh_callback)

        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n  Scheduler stopped.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
