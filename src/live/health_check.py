"""System health monitoring for the live trading environment.

During live sessions the :meth:`HealthChecker.start_live_monitor` method
runs all checks every 60 seconds and auto-alerts via the configured
``AlertManager`` whenever a check fails.
"""

import logging
import os
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional, Tuple

try:
    import psutil as _psutil
except ImportError:  # pragma: no cover
    _psutil = None  # type: ignore[assignment]

from src.live.alerts import AlertManager, ERROR, WARNING

logger = logging.getLogger(__name__)

# IST timezone (UTC+5:30)
_IST = timezone(timedelta(hours=5, minutes=30))
_MARKET_OPEN_H, _MARKET_OPEN_M = 9, 15
_MARKET_CLOSE_H, _MARKET_CLOSE_M = 15, 30


class HealthChecker:
    """Run a battery of health checks and auto-alert on failures.

    Args:
        alert_manager: Optional AlertManager for sending failure notifications.
        data_dir: Path to the data directory for disk-space checks.
        memory_threshold_pct: Memory usage percentage that triggers a warning.
        disk_min_free_mb: Minimum free disk space (MB) in data_dir.
        data_freshness_seconds: Max seconds since last tick before staleness warning.
    """

    def __init__(
        self,
        alert_manager: Optional[AlertManager] = None,
        data_dir: str = "data",
        memory_threshold_pct: float = 90.0,
        disk_min_free_mb: float = 500.0,
        data_freshness_seconds: float = 60.0,
    ) -> None:
        self.alert_manager = alert_manager
        self.data_dir = data_dir
        self.memory_threshold_pct = memory_threshold_pct
        self.disk_min_free_mb = disk_min_free_mb
        self.data_freshness_seconds = data_freshness_seconds

    # ------------------------------------------------------------------
    # Individual checks — each returns (ok, message)
    # ------------------------------------------------------------------

    def check_api_connection(self, kite: Any) -> Tuple[bool, str]:
        """Verify the Kite API session is alive.

        Args:
            kite: A KiteConnect instance (or any object with a `profile()` method).

        Returns:
            (ok, message) tuple.
        """
        try:
            profile = kite.profile()
            user = profile.get("user_name", "unknown") if isinstance(profile, dict) else "ok"
            return True, f"API connected (user={user})"
        except Exception as exc:
            return False, f"API connection failed: {exc}"

    def check_data_freshness(
        self, last_tick_time: Optional[datetime] = None
    ) -> Tuple[bool, str]:
        """Check whether the most recent tick is reasonably fresh.

        Args:
            last_tick_time: Datetime of the last received tick (tz-aware UTC).

        Returns:
            (ok, message) tuple.
        """
        if last_tick_time is None:
            return False, "No tick data received yet"

        now = datetime.now(timezone.utc)
        # Make last_tick_time tz-aware if it isn't already
        if last_tick_time.tzinfo is None:
            last_tick_time = last_tick_time.replace(tzinfo=timezone.utc)
        age_seconds = (now - last_tick_time).total_seconds()

        if age_seconds > self.data_freshness_seconds:
            return False, f"Data stale: last tick {age_seconds:.0f}s ago (limit {self.data_freshness_seconds:.0f}s)"
        return True, f"Data fresh: last tick {age_seconds:.0f}s ago"

    def check_disk_space(self, data_dir: Optional[str] = None) -> Tuple[bool, str]:
        """Check free disk space in the data directory.

        Args:
            data_dir: Override path (defaults to self.data_dir).

        Returns:
            (ok, message) tuple.
        """
        path = data_dir or self.data_dir
        try:
            usage = shutil.disk_usage(path)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < self.disk_min_free_mb:
                return False, f"Low disk space: {free_mb:.0f} MB free (min {self.disk_min_free_mb:.0f} MB)"
            return True, f"Disk OK: {free_mb:.0f} MB free"
        except Exception as exc:
            return False, f"Disk check failed: {exc}"

    def check_memory_usage(self) -> Tuple[bool, str]:
        """Check system memory usage.

        Returns:
            (ok, message) tuple.
        """
        if _psutil is None:
            # Fallback: try reading /proc/meminfo on Linux
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                info = {}
                for line in lines:
                    parts = line.split()
                    info[parts[0].rstrip(":")] = int(parts[1])
                total = info.get("MemTotal", 1)
                available = info.get("MemAvailable", total)
                pct = (1 - available / total) * 100
            except Exception:
                return True, "Memory check skipped (psutil not installed, /proc unavailable)"
        else:
            mem = _psutil.virtual_memory()
            pct = mem.percent

        if pct > self.memory_threshold_pct:
            return False, f"High memory usage: {pct:.1f}% (threshold {self.memory_threshold_pct:.0f}%)"
        return True, f"Memory OK: {pct:.1f}% used"

    # ------------------------------------------------------------------
    # Aggregate
    # ------------------------------------------------------------------

    def run_all_checks(
        self,
        kite: Any = None,
        last_tick_time: Optional[datetime] = None,
    ) -> List[Tuple[str, bool, str]]:
        """Run all health checks and auto-alert on failures.

        Args:
            kite: Optional KiteConnect instance.
            last_tick_time: Optional datetime of last tick.

        Returns:
            List of (check_name, ok, message) tuples.
        """
        results: List[Tuple[str, bool, str]] = []

        if kite is not None:
            ok, msg = self.check_api_connection(kite)
            results.append(("api_connection", ok, msg))

        ok, msg = self.check_data_freshness(last_tick_time)
        results.append(("data_freshness", ok, msg))

        ok, msg = self.check_disk_space()
        results.append(("disk_space", ok, msg))

        ok, msg = self.check_memory_usage()
        results.append(("memory_usage", ok, msg))

        # Auto-alert on failures
        if self.alert_manager is not None:
            for check_name, ok, msg in results:
                if not ok:
                    self.alert_manager.send_alert(
                        WARNING,
                        f"Health check failed: {check_name}",
                        {"detail": msg},
                    )

        return results

    # ------------------------------------------------------------------
    # Live monitoring loop
    # ------------------------------------------------------------------

    @staticmethod
    def _is_market_hours() -> bool:
        """Return True if the current IST time is within market hours."""
        now = datetime.now(_IST)
        if now.weekday() > 4:   # Saturday / Sunday
            return False
        t = now.time()
        from datetime import time as _time
        return (
            _time(_MARKET_OPEN_H, _MARKET_OPEN_M)
            <= t
            <= _time(_MARKET_CLOSE_H, _MARKET_CLOSE_M)
        )

    def start_live_monitor(
        self,
        kite: Any = None,
        interval_seconds: int = 60,
        only_during_market_hours: bool = True,
    ) -> threading.Thread:
        """Run health checks in a background thread every ``interval_seconds``.

        Checks are automatically sent to the configured ``AlertManager`` when
        they fail.  By default the checks only fire during market hours
        (9:15–15:30 IST, weekdays).

        Args:
            kite: Optional authenticated KiteConnect instance.
            interval_seconds: How often to run checks (default 60 s).
            only_during_market_hours: Skip checks outside market hours.

        Returns:
            The daemon Thread that is running the monitor loop.
        """

        def _loop() -> None:
            logger.info(
                "HealthChecker live monitor started (interval=%ds, market-hours-only=%s).",
                interval_seconds,
                only_during_market_hours,
            )
            while True:
                if only_during_market_hours and not self._is_market_hours():
                    time.sleep(interval_seconds)
                    continue

                try:
                    results = self.run_all_checks(kite=kite)
                    failed = [name for name, ok, _ in results if not ok]
                    if failed:
                        logger.warning("Health check failures: %s", ", ".join(failed))
                    else:
                        logger.debug("All health checks passed.")
                except Exception as exc:
                    logger.error("Health monitor loop error: %s", exc)
                    if self.alert_manager is not None:
                        self.alert_manager.send_alert(
                            ERROR,
                            "Health monitor loop crashed",
                            {"error": str(exc)},
                        )

                time.sleep(interval_seconds)

        thread = threading.Thread(target=_loop, name="health-monitor", daemon=True)
        thread.start()
        return thread
