#!/usr/bin/env python3
"""
MyAlgoTrader - Algorithmic Trading Application
Main entry point for the trading application
"""

import argparse
import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from src.kite_client import KiteClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
    result = subprocess.run([sys.executable, 'live_trader_status.py'],
                          cwd=BASE_DIR,
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

def start_oauth_server():
    """Start OAuth callback server for authorization"""
    import subprocess
    print("Starting OAuth callback server...")
    result = subprocess.run([sys.executable, 'oauth_callback_server.py'],
                          cwd=BASE_DIR)
    return result.returncode == 0

def start_https_oauth_server():
    """Start HTTPS OAuth callback server for secure authorization"""
    import subprocess
    print("Starting SECURE HTTPS OAuth callback server...")
    print("Use https://localhost:8443 in your Kite Connect app")
    result = subprocess.run([sys.executable, 'oauth_https_server.py'],
                          cwd=BASE_DIR)
    return result.returncode == 0

def run_backtest(strategy):
    """Run backtest - delegates to backtests/run_backtest.py"""
    import subprocess
    print(f"Running backtest with strategy: {strategy}")
    print(f"You can also run backtests directly: python {os.path.join('backtests', 'run_backtest.py')}")
    result = subprocess.run([sys.executable, os.path.join('backtests', 'run_backtest.py'),
                            '--strategy', strategy],
                          cwd=BASE_DIR,
                          capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

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
                              cwd=BASE_DIR)
    elif args.command == 'live':
        logger.info("Live trading not implemented yet")

if __name__ == "__main__":
    main()
