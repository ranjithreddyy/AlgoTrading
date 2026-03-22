#!/usr/bin/env python3
"""
MyAlgoTrader - Algorithmic Trading Application
Main entry point for the trading application
"""

import argparse
from src.kite_client import KiteClient
import logging
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_connection():
    """Test Kite Connect connection"""
    kite = KiteClient()
    try:
        profile = kite.get_profile()
        logger.info("Connection successful!")
        logger.info(f"User: {profile['user_name']} ({profile['user_id']})")
        logger.info(f"Email: {profile['email']}")
        return True
    except Exception as e:
        logger.error(f"Connection failed: {e}")
        return False

def check_status():
    """Check live trading status"""
    import subprocess
    import sys
    result = subprocess.run([sys.executable, 'live_trader_status.py'],
                          cwd='/home/ranjith/TradingZeroda',
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

def start_https_oauth_server():
    """Start HTTPS OAuth callback server for secure authorization"""
    import subprocess
    import sys
    print("Starting SECURE HTTPS OAuth callback server...")
    print("Use https://localhost:8443 in your Kite Connect app")
    print("⚠️  Browser will show security warning - click 'Advanced' -> 'Proceed to localhost'")
    result = subprocess.run([sys.executable, 'oauth_https_server.py'],
                          cwd='/home/ranjith/TradingZeroda')
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description='MyAlgoTrader - Algorithmic Trading App')
    parser.add_argument('command', choices=['test', 'backtest', 'status', 'oauth', 'https', 'token', 'live'], help='Command to run')
    parser.add_argument('--strategy', default='sma', help='Strategy to use for backtest')

    args = parser.parse_args()

    if args.command == 'test':
        test_connection()
    elif args.command == 'backtest':
        run_backtest(args.strategy)
    elif args.command == 'status':
        check_status()
    elif args.command == 'oauth':
        start_oauth_server()
    elif args.command == 'https':
        start_https_oauth_server()
    elif args.command == 'token':
        import subprocess
        result = subprocess.run([sys.executable, 'token_manager.py'],
                              cwd='/home/ranjith/TradingZeroda')
    elif args.command == 'live':
        logger.info("Live trading not implemented yet")

if __name__ == "__main__":
    main()