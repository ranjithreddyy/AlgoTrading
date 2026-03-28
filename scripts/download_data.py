#!/usr/bin/env python3
"""
Download historical data and instrument masters from Zerodha Kite API.
Saves data as CSV files in data/ directory.
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect
import pandas as pd

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

API_KEY = os.getenv("KITE_API_KEY")
ACCESS_TOKEN = os.getenv("KITE_ACCESS_TOKEN")

kite = KiteConnect(api_key=API_KEY)
kite.set_access_token(ACCESS_TOKEN)


def save_instruments():
    """Download and save full instrument masters for NSE and NFO."""
    today = datetime.now().strftime("%Y-%m-%d")
    inst_dir = DATA_DIR / "raw" / "instruments" / today
    inst_dir.mkdir(parents=True, exist_ok=True)

    for exchange in ["NSE", "NFO"]:
        print(f"Downloading {exchange} instruments...")
        instruments = kite.instruments(exchange)
        df = pd.DataFrame(instruments)
        path = inst_dir / f"{exchange}_instruments.csv"
        df.to_csv(path, index=False)
        print(f"  Saved {len(df)} instruments to {path}")

    return inst_dir


def get_historical(token, symbol, from_date, to_date, interval, exchange="NSE"):
    """Fetch historical data with rate limiting and save to CSV."""
    out_dir = DATA_DIR / "market" / exchange / symbol / interval
    out_dir.mkdir(parents=True, exist_ok=True)

    all_data = []
    # Kite API limits: max 60 days per minute request, 2000 days per day request
    if interval == "day":
        chunk_days = 2000
    elif interval in ("minute", "3minute", "5minute"):
        chunk_days = 60
    elif interval in ("15minute", "30minute", "60minute"):
        chunk_days = 200
    else:
        chunk_days = 60

    current = from_date
    while current < to_date:
        chunk_end = min(current + timedelta(days=chunk_days), to_date)
        try:
            data = kite.historical_data(token, current, chunk_end, interval)
            all_data.extend(data)
            print(f"  {symbol} {interval}: {current.strftime('%Y-%m-%d')} to {chunk_end.strftime('%Y-%m-%d')} -> {len(data)} bars")
        except Exception as e:
            print(f"  ERROR {symbol} {interval} {current.strftime('%Y-%m-%d')}: {e}")
        current = chunk_end + timedelta(days=1)
        time.sleep(0.35)  # rate limit: 3 req/sec

    if all_data:
        df = pd.DataFrame(all_data)
        filename = f"{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}.csv"
        path = out_dir / filename
        df.to_csv(path, index=False)
        print(f"  SAVED {len(df)} bars to {path}")
        return df
    return None


def download_stock_data(symbols, intervals, days_back=365):
    """Download historical data for a list of stock symbols."""
    # Resolve instrument tokens
    print("Resolving instrument tokens...")
    instruments = kite.instruments("NSE")
    token_map = {}
    for inst in instruments:
        if inst["tradingsymbol"] in symbols:
            token_map[inst["tradingsymbol"]] = inst["instrument_token"]

    found = set(token_map.keys())
    missing = set(symbols) - found
    if missing:
        print(f"  WARNING: Could not find tokens for: {missing}")
    print(f"  Resolved {len(token_map)} symbols")

    to_date = datetime.now()
    results = []

    for symbol, token in token_map.items():
        for interval in intervals:
            # Minute data only available for ~60 days on Kite
            if interval == "minute":
                from_date = to_date - timedelta(days=60)
            elif interval in ("3minute", "5minute"):
                from_date = to_date - timedelta(days=100)
            elif interval in ("15minute", "30minute", "60minute"):
                from_date = to_date - timedelta(days=200)
            else:
                from_date = to_date - timedelta(days=days_back)

            print(f"\n--- {symbol} | {interval} | {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')} ---")
            df = get_historical(token, symbol, from_date, to_date, interval)
            if df is not None:
                results.append({
                    "symbol": symbol,
                    "interval": interval,
                    "from": from_date.strftime("%Y-%m-%d"),
                    "to": to_date.strftime("%Y-%m-%d"),
                    "records": len(df),
                })

    return results


def download_nifty_index(days_back=365):
    """Download NIFTY 50 index historical data."""
    token = 256265  # NIFTY 50 instrument token
    to_date = datetime.now()

    results = []
    for interval in ["day", "15minute", "5minute"]:
        if interval in ("5minute",):
            from_date = to_date - timedelta(days=100)
        elif interval in ("15minute",):
            from_date = to_date - timedelta(days=200)
        else:
            from_date = to_date - timedelta(days=days_back)

        print(f"\n--- NIFTY 50 | {interval} | {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')} ---")
        df = get_historical(token, "NIFTY_50", from_date, to_date, interval, exchange="INDEX")
        if df is not None:
            results.append({
                "symbol": "NIFTY 50",
                "interval": interval,
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "records": len(df),
            })

    return results


def main():
    print("=" * 60)
    print("ZERODHA DATA DOWNLOAD")
    print("=" * 60)

    # Step 1: Save instrument masters
    print("\n[1/3] DOWNLOADING INSTRUMENT MASTERS")
    save_instruments()

    # Step 2: Download NIFTY index data
    print("\n[2/3] DOWNLOADING NIFTY 50 INDEX DATA")
    nifty_results = download_nifty_index(days_back=730)

    # Step 3: Download stock data for top liquid names
    print("\n[3/3] DOWNLOADING STOCK DATA")
    top_stocks = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT",
    ]
    stock_results = download_stock_data(
        symbols=top_stocks,
        intervals=["day", "15minute"],
        days_back=730,
    )

    # Summary
    all_results = nifty_results + stock_results
    print("\n" + "=" * 60)
    print("DOWNLOAD SUMMARY")
    print("=" * 60)
    for r in all_results:
        print(f"  {r['symbol']:15s} | {r['interval']:10s} | {r['from']} to {r['to']} | {r['records']:>6} bars")

    # Save summary
    summary_path = DATA_DIR / "download_summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
