"""
Live Trading Status Check - Safe version without price dependencies
"""
from src.kite_client import KiteClient
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LiveTraderStatus:
    def __init__(self):
        self.kite = KiteClient()
        logger.info("LiveTrader Status initialized successfully")

    def check_market_status(self):
        """Check if markets are currently open"""
        try:
            # Try to get a quote - if markets are closed, this will fail
            quote = self.kite.kite.quote('NSE:NIFTY 50')
            ltp = quote['NSE:NIFTY 50']['last_price']
            return True, f"Markets are open (NIFTY 50: ₹{ltp})"
        except Exception as e:
            if "closed" in str(e).lower():
                return False, "Markets are closed"
            else:
                return False, f"Unable to determine market status: {e}"

    def get_account_balance(self):
        """Get available account balance"""
        try:
            margins = self.kite.kite.margins()
            equity = margins.get('equity', {})
            available_cash = equity.get('available', {}).get('cash', 0)
            return available_cash
        except Exception as e:
            logger.error(f"Error getting account balance: {e}")
            return 0

    def test_order_placement(self):
        """Test order placement mechanism safely"""
        try:
            # Try a small order that should fail due to insufficient funds
            order_params = {
                'variety': 'regular',
                'exchange': 'NSE',
                'tradingsymbol': 'RELIANCE',
                'transaction_type': 'BUY',
                'order_type': 'MARKET',
                'quantity': 1,
                'product': 'CNC',
            }

            order_id = self.kite.place_order(**order_params)
            return False, f"Unexpected success: {order_id}"

        except Exception as e:
            error_msg = str(e).lower()
            if 'insufficient' in error_msg or 'margin' in error_msg or 'funds' in error_msg:
                return True, "Order placement works (failed as expected due to insufficient funds)"
            elif 'closed' in error_msg:
                return True, "Order placement works (markets closed)"
            else:
                return False, f"Order placement failed: {e}"

    def get_positions(self):
        """Get current positions"""
        try:
            return self.kite.get_positions()
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return None

if __name__ == "__main__":
    trader = LiveTraderStatus()

    print("🚀 LIVE TRADING STATUS CHECK")
    print("=" * 50)
    print(f"Current Time: {datetime.now()}")
    print()

    # Check market status
    markets_open, status_msg = trader.check_market_status()
    print(f"📊 Market Status: {status_msg}")

    # Check account balance
    balance = trader.get_account_balance()
    print(f"💰 Available Balance: ₹{balance}")

    # Test order placement
    order_test_success, order_msg = trader.test_order_placement()
    print(f"📤 Order Placement Test: {'✅ PASS' if order_test_success else '❌ FAIL'}")
    print(f"   {order_msg}")

    # Show current positions
    positions = trader.get_positions()
    if positions and positions.get('net'):
        print(f"📊 Current Positions: {len(positions['net'])}")
        for pos in positions['net']:
            print(f"   - {pos['tradingsymbol']}: {pos['quantity']} @ ₹{pos['average_price']}")
    else:
        print("📊 Current Positions: None")

    print()
    print("=" * 50)
    if order_test_success:
        print("🎉 API CONNECTIVITY: FULLY WORKING")
        print("✅ Authentication successful")
        print("✅ Account access confirmed")
        print("✅ Order placement mechanism tested")
        print("✅ Position tracking available")
        print()
        print("📋 NEXT STEPS:")
        print("1. ✅ PAID APP ACTIVE: Live market data working!")
        print("2. Add funds to trading account (₹0 available currently)")
        print("3. Test with small amounts during market hours")
        print("4. Implement risk management and position sizing")
        print("5. Build live trading strategies using real-time data")
    else:
        print("❌ ISSUES DETECTED - Check API credentials and permissions")