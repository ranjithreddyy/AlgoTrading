#!/usr/bin/env python3
"""
Fetch historical data from Kite Connect and save to CSV
"""

from src.kite_client import KiteClient
from datetime import datetime, timedelta
import pandas as pd
import os

def fetch_and_save_data(instrument_token, symbol, days=365, interval="day"):
    """Fetch historical data and save to CSV"""
    kite = KiteClient()

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days)

    print(f"Fetching data for {symbol} from {from_date.date()} to {to_date.date()}")

    try:
        data = kite.get_historical_data(instrument_token, from_date, to_date, interval)

        if data:
            df = pd.DataFrame(data)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # Ensure data directory exists
            os.makedirs('data', exist_ok=True)

            filename = f"data/{symbol}_{interval}.csv"
            df.to_csv(filename)
            print(f"Data saved to {filename}")
            print(f"Records: {len(df)}")
            return df
        else:
            print("No data received")
            return None

    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def get_instrument_token(symbol, exchange="NSE"):
    """Get instrument token for a symbol"""
    kite = KiteClient()
    instruments = kite.get_instruments(exchange=exchange)

    for instrument in instruments:
        if instrument['tradingsymbol'] == symbol:
            return instrument['instrument_token']

    print(f"Instrument {symbol} not found in {exchange}")
    return None

if __name__ == "__main__":
    # Example: Fetch NIFTY 50 data
    symbol = "NIFTY 50"
    token = get_instrument_token(symbol, "NSE")

    if token:
        fetch_and_save_data(token, symbol.replace(" ", "_"), days=365)
    else:
        print("Could not find instrument token")