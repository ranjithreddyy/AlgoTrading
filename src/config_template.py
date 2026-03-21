# Configuration template for MyAlgoTrader
# Copy this to config.py and fill in your actual credentials
# NEVER commit config.py to version control

import os

# API credentials from environment variables
# Set these environment variables in your shell:
# export KITE_API_KEY="your_api_key_here"
# export KITE_API_SECRET="your_api_secret_here"
# export KITE_ACCESS_TOKEN="your_access_token_here"  # Optional, obtained after login

API_KEY = os.getenv('KITE_API_KEY')
API_SECRET = os.getenv('KITE_API_SECRET')
REDIRECT_URI = "http://localhost:8000"

# Validate that environment variables are set
if not API_KEY or not API_SECRET:
    raise ValueError("Please set KITE_API_KEY and KITE_API_SECRET environment variables")

# Zerodha user ID (optional, for single user app)
USER_ID = os.getenv('KITE_USER_ID', "your_user_id_here")

# Access token will be obtained during login
ACCESS_TOKEN = os.getenv('KITE_ACCESS_TOKEN')