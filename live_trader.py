#!/usr/bin/env python3
"""
Live Trading Implementation
"""

import time
import logging
from datetime import datetime
from src.kite_client import KiteClient
from strategies.sma_strategy import SimpleMovingAverageStrategy
import backtrader as bt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveTrader:
    def __init__(self, strategy_class, symbol="NIFTY 50", quantity=50, max_orders_per_day=5):
        self.kite = KiteClient()
        self.strategy_class = strategy_class
        self.symbol = symbol
        self.quantity = quantity
        self.max_orders_per_day = max_orders_per_day
        self.orders_today = 0
        self.last_reset_date = datetime.now().date()

        # Get instrument token
        self.instrument_token = self._get_instrument_token(symbol)
        if not self.instrument_token:
            raise ValueError(f"Could not find instrument token for {symbol}")

        logger.info(f"✅ Initialized live trader for {symbol} (token: {self.instrument_token})")

    def _get_instrument_token(self, symbol):
        """Get instrument token for a symbol"""
        instruments = self.kite.get_instruments("NSE")
        for inst in instruments:
            if inst['tradingsymbol'] == symbol:
                return inst['instrument_token']
        return None

    def _reset_daily_counter(self):
        """Reset daily order counter if it's a new day"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.orders_today = 0
            self.last_reset_date = today
            logger.info("📅 Daily order counter reset")

    def _can_place_order(self):
        """Check if we can place an order today"""
        self._reset_daily_counter()
        return self.orders_today < self.max_orders_per_day

    def get_latest_price(self):
        """Get latest price for the symbol"""
        try:
            # Get quote (last traded price)
            quote = self.kite.kite.quote(f"NSE:{self.symbol}")
            ltp = quote[f"NSE:{self.symbol}"]['last_price']
            logger.info(f"📈 {self.symbol} LTP: ₹{ltp}")
            return ltp
        except Exception as e:
            logger.error(f"❌ Failed to get price: {e}")
            return None

    def place_buy_order(self, price=None):
        """Place a buy order"""
        if not self._can_place_order():
            logger.warning("⚠️ Daily order limit reached")
            return None

        try:
            order_params = {
                "variety": "regular",
                "exchange": "NSE",
                "tradingsymbol": self.symbol,
                "transaction_type": "BUY",
                "order_type": "MARKET" if price is None else "LIMIT",
                "quantity": self.quantity,
            }

            if price:
                order_params["price"] = price

            logger.info(f"📤 Placing BUY order: {order_params}")
            response = self.kite.place_order(**order_params)
            self.orders_today += 1

            logger.info(f"✅ BUY order placed: {response}")
            return response

        except Exception as e:
            logger.error(f"❌ Failed to place BUY order: {e}")
            return None

    def place_sell_order(self, price=None):
        """Place a sell order"""
        if not self._can_place_order():
            logger.warning("⚠️ Daily order limit reached")
            return None

        try:
            order_params = {
                "variety": "regular",
                "exchange": "NSE",
                "tradingsymbol": self.symbol,
                "transaction_type": "SELL",
                "order_type": "MARKET" if price is None else "LIMIT",
                "quantity": self.quantity,
            }

            if price:
                order_params["price"] = price

            logger.info(f"📤 Placing SELL order: {order_params}")
            response = self.kite.place_order(**order_params)
            self.orders_today += 1

            logger.info(f"✅ SELL order placed: {response}")
            return response

        except Exception as e:
            logger.error(f"❌ Failed to place SELL order: {e}")
            return None

    def get_current_positions(self):
        """Get current positions"""
        try:
            positions = self.kite.get_positions()
            net_positions = positions.get('net', [])
            logger.info(f"📊 Current positions: {len(net_positions)}")
            for pos in net_positions:
                if pos['tradingsymbol'] == self.symbol:
                    logger.info(f"  {pos['tradingsymbol']}: {pos['quantity']} @ ₹{pos['average_price']}")
            return net_positions
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            return []

    def get_account_balance(self):
        """Get account balance/margins"""
        try:
            margins = self.kite.kite.margins()
            equity = margins.get('equity', {})
            logger.info(f"💰 Available balance: ₹{equity.get('available', {}).get('cash', 0)}")
            return margins
        except Exception as e:
            logger.error(f"❌ Failed to get balance: {e}")
            return None

def test_live_trading():
    """Test live trading functionality"""
    logger.info("🚀 Starting Live Trading Test")
    logger.info("=" * 50)

    # Initialize trader with very small quantity for safety
    trader = LiveTrader(SimpleMovingAverageStrategy, symbol="NIFTY 50", quantity=50)

    # Check account status
    logger.info("📊 Checking account status...")
    trader.get_account_balance()
    trader.get_current_positions()

    # Get current price
    price = trader.get_latest_price()
    if not price:
        logger.error("❌ Cannot get price data. Aborting.")
        return

    # Test order placement (commented out for safety)
    logger.info("⚠️ ORDER PLACEMENT IS COMMENTED OUT FOR SAFETY")
    logger.info("💡 To enable live trading, uncomment the order placement lines below")

    # Uncomment these lines only when ready for live trading
    # logger.info("🧪 Testing BUY order (will be cancelled immediately)...")
    # buy_order = trader.place_buy_order()
    # if buy_order:
    #     logger.info("🧪 Testing SELL order (will be cancelled immediately)...")
    #     sell_order = trader.place_sell_order()

    logger.info("=" * 50)
    logger.info("🎯 Live Trading Test Complete!")
    logger.info("")
    logger.info("📋 To enable actual trading:")
    logger.info("1. Uncomment the order placement lines in this script")
    logger.info("2. Ensure sufficient funds in your trading account")
    logger.info("3. Start with very small quantities")
    logger.info("4. Monitor orders closely")

if __name__ == "__main__":
    test_live_trading()