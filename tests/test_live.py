"""Tests for live trading infrastructure: kill switch, paper broker,
health checks, alerts, and token refresh validation.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.broker.paper_broker import PaperBroker
from src.live.alerts import (
    AlertManager,
    ConsoleAlert,
    FileAlert,
    TelegramAlert,
    WebhookAlert,
    INFO,
    WARNING,
    ERROR,
    CRITICAL,
)
from src.live.health_check import HealthChecker
from src.live.token_refresh import TokenRefreshManager
from src.risk.kill_switch import KillSwitch


# ── KillSwitch tests ─────────────────────────────────────────────────────


class TestKillSwitchPersists:
    """test_kill_switch_persists: save and reload kill switch state."""

    def test_save_and_load_active_state(self, tmp_path):
        ks = KillSwitch()
        ks.activate("drawdown exceeded limit")
        state_file = str(tmp_path / "ks.json")
        ks.save_state(state_file)

        ks2 = KillSwitch()
        ks2.load_state(state_file)

        assert ks2.is_active() is True
        assert ks2.reason == "drawdown exceeded limit"

    def test_save_and_load_inactive_state(self, tmp_path):
        ks = KillSwitch()
        ks.activate("test")
        ks.deactivate()
        state_file = str(tmp_path / "ks.json")
        ks.save_state(state_file)

        ks2 = KillSwitch()
        ks2.load_state(state_file)

        assert ks2.is_active() is False

    def test_log_preserved_across_save_load(self, tmp_path):
        ks = KillSwitch()
        ks.activate("reason A")
        ks.deactivate()
        ks.activate("reason B")
        state_file = str(tmp_path / "ks_log.json")
        ks.save_state(state_file)

        ks2 = KillSwitch()
        ks2.load_state(state_file)

        assert len(ks2.activation_log) == 3  # activate, deactivate, activate
        assert ks2.activation_log[-1]["reason"] == "reason B"

    def test_load_nonexistent_file_is_noop(self, tmp_path):
        ks = KillSwitch()
        ks.load_state(str(tmp_path / "does_not_exist.json"))
        assert ks.is_active() is False

    def test_state_file_is_valid_json(self, tmp_path):
        ks = KillSwitch()
        ks.activate("json check")
        state_file = str(tmp_path / "ks_json.json")
        ks.save_state(state_file)
        data = json.loads(Path(state_file).read_text())
        assert "active" in data
        assert "reason" in data
        assert "log" in data


# ── PaperBroker tests ─────────────────────────────────────────────────────


class TestPaperBrokerState:
    """test_paper_broker_state: save and reload paper broker state."""

    def test_save_and_load_restores_cash(self, tmp_path):
        broker = PaperBroker(initial_capital=100_000)
        broker.place_order("RELIANCE", "BUY", 10, "MARKET", price=2500.0)
        state_file = str(tmp_path / "broker.json")
        broker.save_state(state_file)

        broker2 = PaperBroker()
        broker2.load_state(state_file)

        # Cash should be reduced by the BUY fill
        assert broker2._cash < 100_000
        assert broker2.initial_capital == 100_000

    def test_save_and_load_restores_trade_log(self, tmp_path):
        broker = PaperBroker(initial_capital=200_000)
        broker.place_order("INFY", "BUY", 5, "MARKET", price=1800.0)
        broker.place_order("INFY", "SELL", 5, "MARKET", price=1850.0)
        state_file = str(tmp_path / "broker2.json")
        broker.save_state(state_file)

        broker2 = PaperBroker()
        broker2.load_state(state_file)

        assert len(broker2.get_trade_log()) == 2

    def test_save_and_load_restores_order_counter(self, tmp_path):
        broker = PaperBroker()
        oid1 = broker.place_order("TCS", "BUY", 1, "MARKET", price=4000.0)
        state_file = str(tmp_path / "broker3.json")
        broker.save_state(state_file)

        broker2 = PaperBroker()
        broker2.load_state(state_file)
        oid2 = broker2.place_order("TCS", "SELL", 1, "MARKET", price=4050.0)

        assert broker2._order_counter == 2

    def test_load_nonexistent_file_is_noop(self, tmp_path):
        broker = PaperBroker(initial_capital=500_000)
        broker.load_state(str(tmp_path / "no_file.json"))
        assert broker._cash == 500_000

    def test_balance_after_round_trip(self, tmp_path):
        broker = PaperBroker(initial_capital=50_000)
        state_file = str(tmp_path / "broker_balance.json")
        broker.save_state(state_file)

        broker2 = PaperBroker()
        broker2.load_state(state_file)

        bal = broker2.get_balance()
        assert bal["initial_capital"] == 50_000
        assert bal["cash"] == 50_000


# ── HealthChecker tests ───────────────────────────────────────────────────


class TestHealthChecksRun:
    """test_health_checks_run: all checks execute without crash."""

    def setup_method(self):
        self.checker = HealthChecker()

    def test_check_disk_space_returns_tuple(self, tmp_path):
        ok, msg = self.checker.check_disk_space(str(tmp_path))
        assert isinstance(ok, bool)
        assert isinstance(msg, str)
        assert ok is True  # tmp_path always has space

    def test_check_memory_usage_returns_tuple(self):
        ok, msg = self.checker.check_memory_usage()
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_check_data_freshness_no_data(self):
        ok, msg = self.checker.check_data_freshness(last_tick_time=None)
        assert ok is False
        assert "No tick" in msg

    def test_check_data_freshness_fresh(self):
        now = datetime.now(timezone.utc)
        ok, msg = self.checker.check_data_freshness(last_tick_time=now)
        assert ok is True

    def test_check_data_freshness_stale(self):
        stale = datetime.now(timezone.utc) - timedelta(seconds=120)
        checker = HealthChecker(data_freshness_seconds=60)
        ok, msg = checker.check_data_freshness(last_tick_time=stale)
        assert ok is False
        assert "stale" in msg.lower()

    def test_run_all_checks_no_kite(self):
        results = self.checker.run_all_checks()
        assert isinstance(results, list)
        # Should have at least disk and memory checks
        check_names = [name for name, _, _ in results]
        assert "disk_space" in check_names
        assert "memory_usage" in check_names

    def test_run_all_checks_with_failing_kite(self):
        bad_kite = MagicMock()
        bad_kite.profile.side_effect = Exception("Session expired")
        results = self.checker.run_all_checks(kite=bad_kite)
        api_results = [(n, ok, m) for n, ok, m in results if n == "api_connection"]
        assert len(api_results) == 1
        assert api_results[0][1] is False

    def test_auto_alert_on_failure(self, tmp_path):
        alert_log = str(tmp_path / "alert.log")
        mgr = AlertManager(log_path=alert_log)
        checker = HealthChecker(alert_manager=mgr, data_freshness_seconds=1)
        stale = datetime.now(timezone.utc) - timedelta(seconds=10)
        checker.run_all_checks(last_tick_time=stale)
        # Failure alert should be written to file
        content = Path(alert_log).read_text()
        assert "data_freshness" in content or "WARNING" in content

    def test_live_monitor_starts_thread(self):
        checker = HealthChecker()
        thread = checker.start_live_monitor(
            kite=None,
            interval_seconds=3600,
            only_during_market_hours=False,
        )
        assert thread.is_alive()
        assert thread.daemon is True


# ── Alert / FileAlert tests ───────────────────────────────────────────────


class TestAlertsFileOutput:
    """test_alerts_file_output: FileAlert writes to disk correctly."""

    def test_file_alert_creates_log(self, tmp_path):
        log_path = str(tmp_path / "test_alerts.log")
        alert = FileAlert(log_path=log_path)
        alert.send(WARNING, "Test warning message")
        assert Path(log_path).exists()

    def test_file_alert_appends_multiple_lines(self, tmp_path):
        log_path = str(tmp_path / "multi.log")
        alert = FileAlert(log_path=log_path)
        for level in [INFO, WARNING, ERROR, CRITICAL]:
            alert.send(level, f"Message at level {level}")
        lines = Path(log_path).read_text().strip().splitlines()
        assert len(lines) == 4

    def test_file_alert_includes_level_in_line(self, tmp_path):
        log_path = str(tmp_path / "level.log")
        alert = FileAlert(log_path=log_path)
        alert.send(ERROR, "Something broke")
        content = Path(log_path).read_text()
        assert "[ERROR]" in content
        assert "Something broke" in content

    def test_file_alert_includes_data_json(self, tmp_path):
        log_path = str(tmp_path / "data.log")
        alert = FileAlert(log_path=log_path)
        alert.send(WARNING, "Slippage spike", data={"avg": 0.05, "symbol": "INFY"})
        content = Path(log_path).read_text()
        assert "0.05" in content
        assert "INFY" in content

    def test_alert_manager_routes_info_to_file_only(self, tmp_path):
        log_path = str(tmp_path / "router.log")
        mgr = AlertManager(log_path=log_path)
        mgr.send_alert(INFO, "Info message")
        content = Path(log_path).read_text()
        assert "Info message" in content

    def test_alert_manager_routes_warning_to_file(self, tmp_path):
        log_path = str(tmp_path / "warn.log")
        mgr = AlertManager(log_path=log_path)
        mgr.send_alert(WARNING, "Warning message")
        content = Path(log_path).read_text()
        assert "Warning message" in content


# ── TelegramAlert tests ──────────────────────────────────────────────────


class TestTelegramAlert:
    """Tests for TelegramAlert, primarily the fallback-to-file path."""

    def test_telegram_falls_back_to_file_when_unconfigured(self, tmp_path):
        log_path = str(tmp_path / "tg_fallback.log")
        tg = TelegramAlert(bot_token=None, chat_id=None, fallback_log_path=log_path)
        tg.send(WARNING, "Fallback test")
        content = Path(log_path).read_text()
        assert "Fallback test" in content

    def test_telegram_format_message_contains_emoji(self):
        tg = TelegramAlert(bot_token="fake", chat_id="123")
        from src.live.alerts import _EMOJI
        msg = tg._format_message(WARNING, "test")
        assert _EMOJI[WARNING] in msg

    def test_telegram_format_message_includes_data(self):
        tg = TelegramAlert(bot_token="fake", chat_id="123")
        msg = tg._format_message(ERROR, "boom", {"key": "val"})
        assert "key" in msg
        assert "val" in msg

    def test_telegram_send_with_requests_mocked(self, tmp_path):
        """Verify the Telegram API is called with correct parameters."""
        tg = TelegramAlert(bot_token="TESTTOKEN", chat_id="99999")
        mock_resp = MagicMock()
        mock_resp.ok = True

        with patch("src.live.alerts._requests") as mock_req:
            mock_req.post.return_value = mock_resp
            tg.send(CRITICAL, "Critical alert", {"loss": 50000})

        mock_req.post.assert_called_once()
        call_kwargs = mock_req.post.call_args
        payload = call_kwargs[1]["json"] if call_kwargs[1] else call_kwargs[0][1]
        assert payload["chat_id"] == "99999"
        assert "Critical alert" in payload["text"]

    def test_telegram_send_handles_requests_exception(self):
        """Exceptions during send should not propagate."""
        tg = TelegramAlert(bot_token="TESTTOKEN", chat_id="99999")
        with patch("src.live.alerts._requests") as mock_req:
            mock_req.post.side_effect = ConnectionError("network down")
            # Should not raise
            tg.send(ERROR, "Network test")


# ── TokenRefreshManager tests ─────────────────────────────────────────────


class TestTokenRefreshCheck:
    """test_token_refresh_check: token validation logic."""

    def test_check_token_invalid_when_credentials_missing(self):
        mgr = TokenRefreshManager(api_key="", access_token="")
        assert mgr.check_token_valid() is False

    def test_check_token_calls_kite_api(self):
        """When kiteconnect is available it should call profile()."""
        mgr = TokenRefreshManager(api_key="testkey", access_token="testtoken")
        mock_kite_instance = MagicMock()
        mock_kite_instance.profile.return_value = {"user_name": "TestUser"}
        mock_kite_class = MagicMock(return_value=mock_kite_instance)

        with patch.dict("sys.modules", {"kiteconnect": MagicMock(KiteConnect=mock_kite_class)}):
            result = mgr.check_token_valid()

        assert result is True
        mock_kite_instance.set_access_token.assert_called_once_with("testtoken")
        mock_kite_instance.profile.assert_called_once()

    def test_check_token_returns_false_on_api_exception(self):
        mgr = TokenRefreshManager(api_key="k", access_token="t")
        mock_kite_instance = MagicMock()
        mock_kite_instance.profile.side_effect = Exception("TokenException")
        mock_kite_class = MagicMock(return_value=mock_kite_instance)

        with patch.dict("sys.modules", {"kiteconnect": MagicMock(KiteConnect=mock_kite_class)}):
            result = mgr.check_token_valid()

        assert result is False

    def test_hours_until_expiry_is_positive(self):
        mgr = TokenRefreshManager()
        hours = mgr.hours_until_expiry()
        assert 0 < hours <= 24

    def test_is_near_expiry_false_when_plenty_of_time(self):
        """Should not flag expiry when > warn_hours remain."""
        mgr = TokenRefreshManager(warn_hours=1.0)
        # Simulate midnight still > 1h away by mocking _ist_now
        from datetime import timedelta, timezone
        from src.live import token_refresh as tr

        fake_now_far = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(
            hour=10, minute=0, second=0, microsecond=0
        )
        with patch.object(tr, "_ist_now", return_value=fake_now_far):
            assert mgr.is_near_expiry() is False

    def test_is_near_expiry_true_when_close_to_midnight(self):
        """Should flag expiry when < warn_hours remain before midnight."""
        mgr = TokenRefreshManager(warn_hours=2.0)
        from datetime import timedelta, timezone
        from src.live import token_refresh as tr

        fake_now_near = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(
            hour=23, minute=0, second=0, microsecond=0
        )
        with patch.object(tr, "_ist_now", return_value=fake_now_near):
            assert mgr.is_near_expiry() is True

    def test_save_token_creates_env_entry(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KITE_API_KEY=abc\n")
        mgr = TokenRefreshManager()
        mgr.save_token("NEW_TOKEN_XYZ", path=str(env_file))
        content = env_file.read_text()
        assert "NEW_TOKEN_XYZ" in content

    def test_save_token_updates_existing_entry(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("KITE_ACCESS_TOKEN=OLD_TOKEN\nKITE_API_KEY=abc\n")
        mgr = TokenRefreshManager()
        mgr.save_token("BRAND_NEW_TOKEN", path=str(env_file))
        content = env_file.read_text()
        assert "BRAND_NEW_TOKEN" in content
        assert "OLD_TOKEN" not in content

    def test_get_login_url_contains_api_key(self):
        mgr = TokenRefreshManager(api_key="MY_KEY_123", access_token="")
        url = mgr.get_login_url()
        assert "MY_KEY_123" in url
        assert "kite.zerodha.com" in url

    def test_auto_refresh_returns_false_when_invalid(self):
        mgr = TokenRefreshManager(api_key="", access_token="")
        result = mgr.auto_refresh_if_needed()
        assert result is False

    def test_schedule_daily_refresh_starts_daemon_thread(self):
        mgr = TokenRefreshManager(api_key="k", access_token="t")
        fired = []

        def cb():
            fired.append(True)

        mgr.schedule_daily_refresh(cb)
        assert mgr._scheduler_thread is not None
        assert mgr._scheduler_thread.is_alive()
        assert mgr._scheduler_thread.daemon is True
