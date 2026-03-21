import backtrader as bt
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from strategies.sma_strategy import SimpleMovingAverageStrategy
from src.kite_client import KiteClient

def run_backtest(strategy_class, data, cash=100000, commission=0.001):
    """Run a backtest with the given strategy and data"""

    # Create a cerebro entity
    cerebro = bt.Cerebro()

    # Add a strategy
    cerebro.addstrategy(strategy_class)

    # Create a Data Feed
    data_feed = bt.feeds.PandasData(dataname=data)

    # Add the Data Feed to Cerebro
    cerebro.adddata(data_feed)

    # Set our desired cash start
    cerebro.broker.setcash(cash)

    # Set the commission
    cerebro.broker.setcommission(commission=commission)

    # Print out the starting conditions
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Run over everything
    cerebro.run()

    # Print out the final result
    print('Final Portfolio Value: %.2f' % cerebro.broker.getvalue())

    # Plot the result
    cerebro.plot()

    return cerebro

def load_historical_data_from_kite(instrument_token, days=365):
    """Load historical data from Kite Connect"""
    kite = KiteClient()
    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    data = kite.get_historical_data(instrument_token, from_date, to_date, "day")

    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    df = df[['open', 'high', 'low', 'close', 'volume']]

    return df

def load_sample_data():
    """Load sample data for testing (replace with real data)"""
    # This is sample data - replace with actual historical data
    dates = pd.date_range(start='2023-01-01', end='2023-12-31', freq='D')
    # Create more realistic price movement
    import numpy as np
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(len(dates)) * 2)
    data = {
        'open': prices,
        'high': prices + np.random.rand(len(dates)) * 5,
        'low': prices - np.random.rand(len(dates)) * 5,
        'close': prices + np.random.randn(len(dates)) * 2,
        'volume': [100000 + i*1000 for i in range(len(dates))]
    }
    df = pd.DataFrame(data, index=dates)
    return df

def load_csv_data(filename):
    """Load data from CSV file"""
    try:
        df = pd.read_csv(filename, index_col='date', parse_dates=True)
        return df
    except FileNotFoundError:
        print(f"File {filename} not found, using sample data")
        return load_sample_data()

if __name__ == "__main__":
    # Try to load real data first, fallback to sample
    data = load_csv_data("data/NIFTY_50_day.csv")
    if data is None or data.empty:
        data = load_sample_data()

    # Run backtest
    cerebro = run_backtest(SimpleMovingAverageStrategy, data)