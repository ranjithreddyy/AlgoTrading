#!/usr/bin/env python
"""system_status.py – Full system health dashboard for TradingZeroda.

Prints a formatted status report covering:
  - API connection
  - Access token validity / expiry
  - Market data freshness
  - Instruments sync info
  - Saved models
  - Paper broker state
  - Kill switch state
  - Disk space
  - Recent alerts

Usage:
    python scripts/system_status.py
"""

import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Suppress library logging noise
import logging
logging.disable(logging.CRITICAL)

from src.config.settings import (
    KITE_API_KEY,
    KITE_ACCESS_TOKEN,
    DATA_DIR,
    ARTIFACTS_DIR,
)
from src.live.token_refresh import TokenRefreshManager

_IST = timezone(timedelta(hours=5, minutes=30))


# ── Colour helpers ──────────────────────────────────────────────────────
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _ok(text: str) -> str:
    return f"{_GREEN}{text}{_RESET}"


def _warn(text: str) -> str:
    return f"{_YELLOW}{text}{_RESET}"


def _fail(text: str) -> str:
    return f"{_RED}{text}{_RESET}"


def _bold(text: str) -> str:
    return f"{_BOLD}{text}{_RESET}"


def _fmt(label: str, value: str, width: int = 20) -> str:
    return f"  {label:<{width}}{value}"


# ── Individual checks ───────────────────────────────────────────────────

def check_api_connection() -> tuple[bool, str]:
    """Attempt a live Kite API call."""
    if not KITE_API_KEY or not KITE_ACCESS_TOKEN:
        return False, _fail("FAIL") + " (credentials missing)"
    try:
        from kiteconnect import KiteConnect  # type: ignore
        kite = KiteConnect(api_key=KITE_API_KEY)
        kite.set_access_token(KITE_ACCESS_TOKEN)
        profile = kite.profile()
        user = profile.get("user_name", "?") if isinstance(profile, dict) else "ok"
        return True, _ok(f"OK ({user})")
    except ImportError:
        return False, _warn("SKIP (kiteconnect not installed)")
    except Exception as exc:
        return False, _fail(f"FAIL ({exc})")


def check_access_token() -> tuple[bool, str]:
    """Validate token and report expiry."""
    mgr = TokenRefreshManager(api_key=KITE_API_KEY, access_token=KITE_ACCESS_TOKEN)
    is_valid = mgr.check_token_valid()
    hours = mgr.hours_until_expiry()

    if is_valid:
        if hours < 2:
            return True, _warn(f"Valid – expires in {hours:.1f}h  (WARNING: near midnight!)")
        return True, _ok(f"Valid – expires in {hours:.1f}h")
    else:
        return False, _fail(f"Expired / Invalid (midnight IST in {hours:.1f}h)")


def check_data_freshness() -> tuple[bool, str]:
    """Report the most recent OHLCV file date."""
    nse_dir = DATA_DIR / "market" / "NSE"
    if not nse_dir.exists():
        return False, _fail("No market data directory found")

    latest_date = None
    for csv in nse_dir.rglob("*.csv"):
        try:
            mtime = datetime.fromtimestamp(csv.stat().st_mtime, tz=timezone.utc)
            if latest_date is None or mtime > latest_date:
                latest_date = mtime
        except OSError:
            pass

    if latest_date is None:
        return False, _fail("No CSV files found")

    date_str = latest_date.astimezone(_IST).strftime("%Y-%m-%d")
    today = datetime.now(_IST).date()
    days_old = (today - latest_date.astimezone(_IST).date()).days
    if days_old == 0:
        return True, _ok(f"Last update {date_str} (today)")
    elif days_old == 1:
        return True, _warn(f"Last update {date_str} (yesterday)")
    else:
        return False, _fail(f"Last update {date_str} ({days_old} days ago)")


def check_instruments() -> tuple[bool, str]:
    """Report instrument counts and last sync date."""
    instruments_dir = DATA_DIR / "raw" / "instruments"
    if not instruments_dir.exists():
        return False, _fail("No instruments directory")

    # Find latest sync date (sorted directory names YYYY-MM-DD)
    date_dirs = sorted(
        [d for d in instruments_dir.iterdir() if d.is_dir()],
        key=lambda d: d.name,
        reverse=True,
    )
    if not date_dirs:
        return False, _fail("No sync dates found")

    latest = date_dirs[0]
    sync_date = latest.name

    nse_csv = latest / "NSE_instruments.csv"
    nfo_csv = latest / "NFO_instruments.csv"

    nse_count = 0
    nfo_count = 0
    if nse_csv.exists():
        nse_count = sum(1 for _ in nse_csv.open()) - 1  # subtract header
    if nfo_csv.exists():
        nfo_count = sum(1 for _ in nfo_csv.open()) - 1

    msg = (
        f"{_ok(f'{nse_count:,} NSE')} / "
        f"{_ok(f'{nfo_count:,} NFO')} "
        f"(last sync: {sync_date})"
    )
    return True, msg


def check_models() -> tuple[bool, str]:
    """Count saved models and report most recent training date."""
    models_dir = ARTIFACTS_DIR / "models"
    if not models_dir.exists():
        return False, _fail("No models directory")

    model_files = list(models_dir.rglob("model.joblib"))
    count = len(model_files)
    if count == 0:
        return False, _fail("0 models saved")

    # Find latest creation time via metadata.json
    latest_trained = None
    latest_algo = None
    for meta_file in models_dir.rglob("metadata.json"):
        try:
            meta = json.loads(meta_file.read_text())
            created_at = meta.get("created_at", "")
            if created_at:
                dt = datetime.fromisoformat(created_at)
                if latest_trained is None or dt > latest_trained:
                    latest_trained = dt
                    latest_algo = meta.get("name", "?")
        except Exception:
            pass

    if latest_trained:
        date_str = latest_trained.strftime("%Y-%m-%d %H:%M")
        return True, _ok(f"{count} model(s) saved / last trained: {date_str} ({latest_algo})")
    return True, _ok(f"{count} model(s) saved / last trained: unknown")


def check_paper_broker() -> tuple[bool, str]:
    """Load paper broker state if it exists."""
    state_path = ARTIFACTS_DIR / "paper_broker_state.json"
    if not state_path.exists():
        return True, _warn("No saved state (fresh / never run)")

    try:
        state = json.loads(state_path.read_text())
        capital = state.get("initial_capital", 0)
        cash = state.get("cash", 0)
        positions_val = sum(
            pos.get("avg_price", 0) * abs(pos.get("quantity", 0))
            for pos in state.get("positions", {}).values()
        )
        pnl = round(cash + positions_val - capital, 2)
        trades = len(state.get("trade_log", []))
        pnl_str = _ok(f"+{pnl:,.2f}") if pnl >= 0 else _fail(f"{pnl:,.2f}")
        return True, (
            f"Capital: Rs {capital:,.0f} / "
            f"PnL: Rs {pnl_str} / "
            f"Trades: {trades}"
        )
    except Exception as exc:
        return False, _fail(f"Error reading state: {exc}")


def check_kill_switch() -> tuple[bool, str]:
    """Load kill switch state."""
    state_path = ARTIFACTS_DIR / "kill_switch_state.json"
    if not state_path.exists():
        return True, _ok("INACTIVE (no saved state)")

    try:
        state = json.loads(state_path.read_text())
        active = state.get("active", False)
        reason = state.get("reason", "")
        if active:
            return False, _fail(f"ACTIVE – {reason}")
        return True, _ok("INACTIVE")
    except Exception as exc:
        return False, _fail(f"Error reading state: {exc}")


def check_disk_space() -> tuple[bool, str]:
    """Report free disk space."""
    try:
        path = str(DATA_DIR) if DATA_DIR.exists() else str(REPO_ROOT)
        usage = shutil.disk_usage(path)
        free_gb = usage.free / (1024 ** 3)
        total_gb = usage.total / (1024 ** 3)
        used_pct = (usage.used / usage.total) * 100
        if free_gb < 1.0:
            status = _fail(f"{free_gb:.1f} GB free / {total_gb:.0f} GB total ({used_pct:.0f}% used)")
        elif free_gb < 5.0:
            status = _warn(f"{free_gb:.1f} GB free / {total_gb:.0f} GB total ({used_pct:.0f}% used)")
        else:
            status = _ok(f"{free_gb:.1f} GB free / {total_gb:.0f} GB total ({used_pct:.0f}% used)")
        return True, status
    except Exception as exc:
        return False, _fail(f"Error: {exc}")


def get_recent_alerts(n: int = 5) -> list[str]:
    """Read last N alerts from the alerts log."""
    log_path = ARTIFACTS_DIR / "alerts" / "alerts.log"
    if not log_path.exists():
        return ["(no alerts log found)"]

    try:
        lines = log_path.read_text().strip().splitlines()
        if not lines:
            return ["(alerts log is empty)"]
        return lines[-n:]
    except Exception as exc:
        return [f"(error reading alerts: {exc})"]


# ── Main dashboard ───────────────────────────────────────────────────────

def main() -> None:
    now_ist = datetime.now(_IST).strftime("%Y-%m-%d %H:%M:%S IST")

    print()
    print(_bold("=" * 56))
    print(_bold("  SYSTEM STATUS DASHBOARD"))
    print(f"  Generated: {now_ist}")
    print(_bold("=" * 56))

    checks = [
        ("API Connection",  check_api_connection),
        ("Access Token",    check_access_token),
        ("Data Freshness",  check_data_freshness),
        ("Instruments",     check_instruments),
        ("Models",          check_models),
        ("Paper Broker",    check_paper_broker),
        ("Kill Switch",     check_kill_switch),
        ("Disk Space",      check_disk_space),
    ]

    all_ok = True
    for label, fn in checks:
        try:
            ok, value = fn()
        except Exception as exc:
            ok, value = False, _fail(f"ERROR: {exc}")
        all_ok = all_ok and ok
        print(_fmt(label + ":", value))

    print()
    print(_bold("  Last 5 Alerts:"))
    for alert_line in get_recent_alerts(5):
        print(f"    {alert_line}")

    print()
    if all_ok:
        print(_bold(_ok("  Overall: ALL SYSTEMS OPERATIONAL")))
    else:
        print(_bold(_warn("  Overall: SOME CHECKS REQUIRE ATTENTION")))
    print(_bold("=" * 56))
    print()


if __name__ == "__main__":
    main()
