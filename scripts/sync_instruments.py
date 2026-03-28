#!/usr/bin/env python3
"""
Download NSE and NFO instrument masters from Zerodha Kite API and save locally.

Usage:
    python scripts/sync_instruments.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

# Ensure project root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.instruments.instrument_master import InstrumentMaster


def main():
    api_key = os.getenv("KITE_API_KEY")
    access_token = os.getenv("KITE_ACCESS_TOKEN")

    if not api_key or not access_token:
        print("ERROR: Set KITE_API_KEY and KITE_ACCESS_TOKEN environment variables.")
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    today = datetime.now().strftime("%Y-%m-%d")
    master = InstrumentMaster()

    print("=" * 60)
    print(f"INSTRUMENT SYNC - {today}")
    print("=" * 60)

    for exchange in ["NSE", "NFO"]:
        print(f"\nDownloading {exchange} instruments...")
        path = master.download_and_save(kite, exchange, date=today)
        print(f"  Saved to {path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total instruments loaded: {len(master.df)}")

    for exchange in master.df["exchange"].unique():
        count = len(master.df[master.df["exchange"] == exchange])
        print(f"  {exchange}: {count}")

    # Segment breakdown
    print("\nSegment breakdown:")
    for segment in sorted(master.df["segment"].unique()):
        count = len(master.df[master.df["segment"] == segment])
        print(f"  {segment}: {count}")

    # Instrument type breakdown
    print("\nInstrument types:")
    for itype in sorted(master.df["instrument_type"].unique()):
        count = len(master.df[master.df["instrument_type"] == itype])
        print(f"  {itype}: {count}")

    print("\nDone.")


if __name__ == "__main__":
    main()
