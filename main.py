#!/usr/bin/env python3
"""
MyAlgoTrader - Algorithmic Trading Application
Main entry point for the trading application
"""

import argparse
from src.kite_client import KiteClient
import logging

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

def run_backtest(strategy_name):
    """Run a backtest"""
    from backtests.run_backtest import run_backtest
    from strategies.sma_strategy import SimpleMovingAverageStrategy

    strategies = {
        'sma': SimpleMovingAverageStrategy,
    }

    if strategy_name not in strategies:
        logger.error(f"Strategy {strategy_name} not found")
        return

    # Load sample data for now
    from backtests.run_backtest import load_sample_data
    data = load_sample_data()

    run_backtest(strategies[strategy_name], data)

def main():
    parser = argparse.ArgumentParser(description='MyAlgoTrader - Algorithmic Trading App')
    parser.add_argument('command', choices=['test', 'backtest', 'live'], help='Command to run')
    parser.add_argument('--strategy', default='sma', help='Strategy to use for backtest')

    args = parser.parse_args()

    if args.command == 'test':
        test_connection()
    elif args.command == 'backtest':
        run_backtest(args.strategy)
    elif args.command == 'live':
        logger.info("Live trading not implemented yet")

if __name__ == "__main__":
    main()