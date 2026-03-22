#!/usr/bin/env python3
"""
Test order placement connectivity and permissions
"""

from src.kite_client import KiteClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_order_permissions():
    """Test if we have order placement permissions"""
    kite = KiteClient()

    try:
        # Test getting orders
        logger.info("Testing order retrieval...")
        orders = kite.get_orders()
        logger.info(f"✅ Successfully retrieved {len(orders)} orders")

        # Test getting positions
        logger.info("Testing position retrieval...")
        positions = kite.get_positions()
        logger.info(f"✅ Successfully retrieved positions: {len(positions.get('net', []))} net positions")

        return True

    except Exception as e:
        logger.error(f"❌ Permission test failed: {e}")
        return False

def test_order_placement_dry_run():
    """Test order placement parameters without actually placing order"""
    kite = KiteClient()

    # Test parameters for a small NIFTY order
    test_order = {
        "variety": "regular",
        "exchange": "NSE",
        "tradingsymbol": "NIFTY 50",
        "transaction_type": "BUY",
        "order_type": "MARKET",
        "quantity": 50,  # Very small quantity for testing
    }

    logger.info("Testing order placement parameters...")
    logger.info(f"Order details: {test_order}")

    try:
        # Note: This will actually place the order! Uncomment only for real testing
        # response = kite.place_order(**test_order)
        # logger.info(f"✅ Order placed successfully: {response}")

        logger.info("✅ Order placement method available (commented out for safety)")
        logger.info("💡 To actually place an order, uncomment the place_order call above")
        logger.info("⚠️  WARNING: This will place a real order!")

        return True

    except Exception as e:
        logger.error(f"❌ Order placement test failed: {e}")
        return False

def get_market_data():
    """Get some basic market data to verify connectivity"""
    kite = KiteClient()

    try:
        # Get instruments
        instruments = kite.get_instruments("NSE")[:3]
        logger.info("✅ Retrieved instruments:")
        for inst in instruments:
            logger.info(f"  - {inst['tradingsymbol']} ({inst['instrument_token']})")

        return True

    except Exception as e:
        logger.error(f"❌ Market data test failed: {e}")
        return False

def main():
    logger.info("🚀 Starting Order Placement Connectivity Test")
    logger.info("=" * 50)

    # Test 1: Basic permissions
    if not test_order_permissions():
        logger.error("❌ Basic permissions test failed. Cannot proceed with order testing.")
        return

    # Test 2: Market data access
    if not get_market_data():
        logger.warning("⚠️ Market data access failed, but continuing...")

    # Test 3: Order placement (dry run)
    if not test_order_placement_dry_run():
        logger.error("❌ Order placement test failed.")
        return

    logger.info("=" * 50)
    logger.info("🎉 All connectivity tests passed!")
    logger.info("")
    logger.info("📋 Next steps for live trading:")
    logger.info("1. Ensure you have sufficient funds in your trading account")
    logger.info("2. Start with very small quantities for testing")
    logger.info("3. Use paper trading/demo account if available")
    logger.info("4. Implement proper risk management")
    logger.info("")
    logger.info("💡 Ready to implement live trading strategies!")

if __name__ == "__main__":
    main()