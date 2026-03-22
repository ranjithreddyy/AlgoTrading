from kiteconnect import KiteConnect, KiteTicker
from src.config import API_KEY, API_SECRET, ACCESS_TOKEN
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KiteClient:
    def __init__(self):
        self.kite = KiteConnect(api_key=API_KEY)
        if ACCESS_TOKEN:
            self.kite.set_access_token(ACCESS_TOKEN)
        self.ticker = None

    def login_url(self):
        """Get the login URL for authentication"""
        return self.kite.login_url()

    def generate_session(self, request_token):
        """Generate session and set access token"""
        data = self.kite.generate_session(request_token, api_secret=API_SECRET)
        self.kite.set_access_token(data["access_token"])
        logger.info("Session generated successfully!")
        logger.info(f"Access Token: {data['access_token']}")
        logger.info("Set this as environment variable: export KITE_ACCESS_TOKEN='%s'" % data['access_token'])
        return data

    def get_profile(self):
        """Get user profile"""
        return self.kite.profile()

    def get_instruments(self, exchange="NSE"):
        """Get instruments for an exchange"""
        return self.kite.instruments(exchange=exchange)

    def get_historical_data(self, instrument_token, from_date, to_date, interval="day"):
        """Get historical data"""
        return self.kite.historical_data(instrument_token, from_date, to_date, interval)

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, order_type, quantity, product, price=None, trigger_price=None):
        """Place an order"""
        order_params = {
            "variety": variety,
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "transaction_type": transaction_type,
            "order_type": order_type,
            "quantity": quantity,
            "product": product,
        }
        if price:
            order_params["price"] = price
        if trigger_price:
            order_params["trigger_price"] = trigger_price

        return self.kite.place_order(**order_params)

    def get_orders(self):
        """Get order history"""
        return self.kite.orders()

    def get_positions(self):
        """Get current positions"""
        return self.kite.positions()

    def start_ticker(self, instruments, on_ticks_callback):
        """Start websocket ticker for real-time data"""
        self.ticker = KiteTicker(API_KEY, ACCESS_TOKEN)

        def on_connect(ws, response):
            logger.info("Ticker connected")
            ws.subscribe(instruments)
            ws.set_mode(ws.MODE_LTP, instruments)

        def on_ticks(ws, ticks):
            on_ticks_callback(ticks)

        self.ticker.on_connect = on_connect
        self.ticker.on_ticks = on_ticks
        self.ticker.connect(threaded=True)

    def stop_ticker(self):
        """Stop the ticker"""
        if self.ticker:
            self.ticker.close()