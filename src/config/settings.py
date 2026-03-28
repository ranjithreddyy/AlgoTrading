"""Centralized settings loaded from .env and sensible defaults."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Auto-detect repo root (two levels up from this file: src/config/settings.py)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env from repo root
load_dotenv(REPO_ROOT / ".env")

# --- Kite / Zerodha credentials ---
KITE_API_KEY: str = os.getenv("KITE_API_KEY", "")
KITE_API_SECRET: str = os.getenv("KITE_API_SECRET", "")
KITE_ACCESS_TOKEN: str = os.getenv("KITE_ACCESS_TOKEN", "")
KITE_USER_ID: str = os.getenv("KITE_USER_ID", "")
REDIRECT_URL: str = os.getenv("REDIRECTURL", "http://127.0.0.1:5000/")

# --- Paths ---
DATA_DIR: Path = REPO_ROOT / "data"
ARTIFACTS_DIR: Path = REPO_ROOT / "artifacts"

# --- Rate limits ---
RATE_LIMIT_HISTORICAL: int = 3  # requests per second

# --- Portfolio ---
BASE_NOTIONAL: int = 500_000  # INR
