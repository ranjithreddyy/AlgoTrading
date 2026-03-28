#!/usr/bin/env python3
"""
CLI script for historical data ingestion.

Usage examples:
    python scripts/ingest_history.py --symbols RELIANCE --intervals day --days-back 30
    python scripts/ingest_history.py --symbols top10 --intervals day,15minute --days-back 365
    python scripts/ingest_history.py --symbols RELIANCE,TCS --validate-only
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

# Ensure project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")

from src.data.storage import DataStorage
from src.data.quality import validate_bars

TOP10_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Ingest historical OHLCV data from Zerodha Kite API")
    parser.add_argument(
        "--symbols",
        type=str,
        default="top10",
        help='Comma-separated symbols or "top10" for default liquid stocks (default: top10)',
    )
    parser.add_argument(
        "--exchange",
        type=str,
        default="NSE",
        help="Exchange (default: NSE)",
    )
    parser.add_argument(
        "--intervals",
        type=str,
        default="day,15minute",
        help="Comma-separated intervals (default: day,15minute)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=365,
        help="Number of days of history to fetch (default: 365)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing data quality, do not fetch",
    )
    return parser.parse_args()


def run_validation(symbols, exchange, intervals, storage):
    """Validate existing data and print quality report."""
    print("\n" + "=" * 70)
    print("DATA QUALITY VALIDATION")
    print("=" * 70)

    for symbol in symbols:
        for interval in intervals:
            if not storage.has_data(symbol, exchange, interval):
                print(f"  {symbol:15s} | {interval:10s} | NO DATA")
                continue

            df = storage.load_bars(symbol, exchange, interval)
            is_valid, issues = validate_bars(df)
            date_range = storage.get_date_range(symbol, exchange, interval)

            status = "OK" if is_valid else "ISSUES"
            dr_str = ""
            if date_range:
                dr_str = f" | {date_range[0].strftime('%Y-%m-%d')} to {date_range[1].strftime('%Y-%m-%d')}"

            print(f"  {symbol:15s} | {interval:10s} | {len(df):>6} bars | {status}{dr_str}")
            if issues:
                for issue in issues:
                    print(f"    -> {issue}")


def run_ingestion(symbols, exchange, intervals, days_back):
    """Run full ingestion pipeline."""
    from kiteconnect import KiteConnect
    from src.data.historical_loader import HistoricalLoader
    from src.data.ingestion import IngestPipeline

    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if not api_key or not access_token:
        print("ERROR: KITE_API_KEY and KITE_ACCESS_TOKEN must be set in .env")
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    storage = DataStorage(str(REPO_ROOT / "data"))
    loader = HistoricalLoader(kite)
    pipeline = IngestPipeline(kite, storage, loader)

    to_date = datetime.now()
    from_date = to_date - timedelta(days=days_back)

    print(f"\nIngesting {len(symbols)} symbols x {len(intervals)} intervals")
    print(f"Date range: {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
    print(f"Exchange: {exchange}")

    results = pipeline.ingest_batch(symbols, exchange, intervals, from_date, to_date)

    # Print summary
    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)
    print(f"  {'Symbol':15s} | {'Interval':10s} | {'Bars':>8s} | Status")
    print(f"  {'-'*15} | {'-'*10} | {'-'*8} | {'-'*20}")

    for r in results:
        status = "OK" if not r["issues"] else "; ".join(r["issues"][:2])
        print(f"  {r['symbol']:15s} | {r['interval']:10s} | {r['bars']:>8d} | {status}")

    total_bars = sum(r["bars"] for r in results)
    print(f"\n  Total: {total_bars} bars ingested")

    return results


def main():
    args = parse_args()

    # Resolve symbols
    if args.symbols.lower() == "top10":
        symbols = TOP10_STOCKS
    else:
        symbols = [s.strip().upper() for s in args.symbols.split(",")]

    intervals = [i.strip() for i in args.intervals.split(",")]
    storage = DataStorage(str(REPO_ROOT / "data"))

    if args.validate_only:
        run_validation(symbols, args.exchange, intervals, storage)
    else:
        run_ingestion(symbols, args.exchange, intervals, args.days_back)
        # Also run validation on newly ingested data
        run_validation(symbols, args.exchange, intervals, storage)


if __name__ == "__main__":
    main()
