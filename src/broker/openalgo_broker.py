"""OpenAlgo broker integration.

OpenAlgo (https://github.com/marketcalls/openalgo) is a free self-hosted
broker API gateway supporting 30+ Indian brokers including Zerodha.

Features:
- Paper trading via API Analyzer Mode (1 Crore virtual capital)
- Same API for paper and live — just toggle OPENALGO_PAPER_MODE in .env
- Unified API across all supported brokers

Setup:
    git clone https://github.com/marketcalls/openalgo
    cd openalgo && pip install -r requirements.txt
    python app.py  # starts on http://localhost:5000

.env keys:
    OPENALGO_API_KEY=your_openalgo_api_key
    OPENALGO_BASE_URL=http://localhost:5000
    OPENALGO_PAPER_MODE=true     # false for live orders
    OPENALGO_EXCHANGE=NSE        # default exchange
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from src.broker.base import Broker

load_dotenv()
logger = logging.getLogger(__name__)


class OpenAlgoBroker(Broker):
    """Broker implementation that routes orders through a local OpenAlgo instance.

    In paper mode (OPENALGO_PAPER_MODE=true), OpenAlgo uses its built-in
    API Analyzer with Rs 1 Crore virtual capital. In live mode it routes to
    the configured broker (e.g. Zerodha Kite).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        paper_mode: Optional[bool] = None,
        exchange: str = "NSE",
    ) -> None:
        self.api_key = api_key or os.getenv("OPENALGO_API_KEY", "")
        self.base_url = (base_url or os.getenv("OPENALGO_BASE_URL", "http://localhost:5000")).rstrip("/")
        _paper_env = os.getenv("OPENALGO_PAPER_MODE", "true").lower()
        self.paper_mode = paper_mode if paper_mode is not None else (_paper_env != "false")
        self.exchange = exchange
        self._session = None  # lazy requests.Session

        mode = "PAPER" if self.paper_mode else "LIVE"
        logger.info(f"OpenAlgoBroker initialized [{mode}] → {self.base_url}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_session(self):
        """Lazy-init a requests.Session with auth headers."""
        if self._session is None:
            try:
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                })
            except ImportError:
                raise RuntimeError("requests library not installed. Run: pip install requests")
        return self._session

    def _post(self, endpoint: str, payload: dict) -> dict:
        """POST to OpenAlgo REST API and return JSON response."""
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        try:
            resp = self._get_session().post(url, json=payload, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"OpenAlgo POST {endpoint} failed: {e}")
            raise

    def _get(self, endpoint: str) -> dict:
        """GET from OpenAlgo REST API and return JSON response."""
        url = f"{self.base_url}/api/v1/{endpoint.lstrip('/')}"
        try:
            resp = self._get_session().get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"OpenAlgo GET {endpoint} failed: {e}")
            raise

    def _is_reachable(self) -> bool:
        """Quick health check — returns True if OpenAlgo is running."""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/", timeout=3)
            return resp.status_code < 500
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Broker interface
    # ------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        order_type: str,
        price: Optional[float] = None,
    ) -> str:
        """Place an order via OpenAlgo.

        OpenAlgo order endpoint: POST /api/v1/placeorder
        Docs: https://docs.openalgo.in/
        """
        payload = {
            "apikey": self.api_key,
            "strategy": "TradingZeroda",
            "symbol": symbol,
            "action": side.upper(),          # BUY or SELL
            "exchange": self.exchange,
            "pricetype": order_type.upper(), # MARKET, LIMIT, SL, SL-M
            "product": "MIS",                # intraday
            "quantity": str(quantity),
        }
        if price and order_type.upper() in ("LIMIT", "SL"):
            payload["price"] = str(round(price, 2))

        if self.paper_mode:
            # Paper mode: simulate locally without hitting OpenAlgo
            order_id = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
            logger.info(f"[PAPER] {side} {quantity} {symbol} @ {price or 'MKT'} → {order_id}")
            return order_id

        result = self._post("placeorder", payload)
        order_id = result.get("orderid", result.get("data", {}).get("orderid", "UNKNOWN"))
        logger.info(f"[LIVE] {side} {quantity} {symbol} → order_id={order_id}")
        return str(order_id)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        if self.paper_mode:
            logger.info(f"[PAPER] Cancel order {order_id}")
            return True
        try:
            result = self._post("cancelorder", {
                "apikey": self.api_key,
                "strategy": "TradingZeroda",
                "orderid": order_id,
            })
            return result.get("status") == "success"
        except Exception:
            return False

    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Get status for a specific order."""
        if self.paper_mode:
            return {"orderid": order_id, "status": "COMPLETE", "mode": "paper"}
        try:
            return self._get(f"orderstatus?orderid={order_id}&apikey={self.api_key}")
        except Exception as e:
            return {"orderid": order_id, "status": "UNKNOWN", "error": str(e)}

    def get_positions(self) -> List[Dict[str, Any]]:
        """Get current open positions."""
        if self.paper_mode:
            return []
        try:
            result = self._get(f"positions?apikey={self.api_key}")
            return result.get("data", [])
        except Exception:
            return []

    def get_orders(self) -> List[Dict[str, Any]]:
        """Get all orders for the day."""
        if self.paper_mode:
            return []
        try:
            result = self._get(f"orderbook?apikey={self.api_key}")
            return result.get("data", [])
        except Exception:
            return []

    def get_balance(self) -> Dict[str, Any]:
        """Get account balance / margin."""
        if self.paper_mode:
            return {"available": 100_00_000, "used": 0, "mode": "paper (1 Crore virtual capital)"}
        try:
            result = self._get(f"funds?apikey={self.api_key}")
            return result.get("data", {})
        except Exception:
            return {"available": 0, "error": "Could not fetch balance"}

    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get live quote for a symbol (extra utility method)."""
        try:
            result = self._post("quotes", {
                "apikey": self.api_key,
                "symbol": symbol,
                "exchange": self.exchange,
            })
            return result.get("data", {})
        except Exception as e:
            return {"symbol": symbol, "error": str(e)}

    def close_all_positions(self) -> bool:
        """Close all open positions (useful for EOD flatten)."""
        if self.paper_mode:
            logger.info("[PAPER] Close all positions — no-op")
            return True
        try:
            result = self._post("closeposition", {
                "apikey": self.api_key,
                "strategy": "TradingZeroda",
            })
            return result.get("status") == "success"
        except Exception:
            return False

    def is_connected(self) -> bool:
        """Check if OpenAlgo is reachable."""
        return self._is_reachable()
