#!/usr/bin/env python3
"""
Token Manager - Check and refresh Kite Connect access tokens
"""

import os
import sys
from datetime import datetime, timedelta
from src.kite_client import KiteClient

def check_token_status():
    """Check if the current access token is valid"""
    print('🔍 CHECKING ACCESS TOKEN STATUS')
    print('=' * 50)

    # Check if token exists
    token = os.getenv('KITE_ACCESS_TOKEN')
    if not token:
        print('❌ No access token found in environment')
        return False

    try:
        kite = KiteClient()
        profile = kite.get_profile()
        print('✅ Access token is VALID')
        print(f'   User: {profile["user_name"]}')
        print(f'   Token: {token[:20]}...')

        # Test live data access
        try:
            quote = kite.kite.quote('NSE:NIFTY 50')
            ltp = quote['NSE:NIFTY 50']['last_price']
            print(f'✅ Live data access: NIFTY 50 = ₹{ltp}')
        except:
            print('⚠️  Live data access failed (might be market closed)')

        return True

    except Exception as e:
        print(f'❌ Access token is INVALID: {e}')
        return False

def refresh_token():
    """Guide user through token refresh process"""
    print('🔄 TOKEN REFRESH PROCESS')
    print('=' * 50)
    print('Your access token has expired. Follow these steps:')
    print()
    print('1. Start the HTTPS OAuth server:')
    print('   python main.py https')
    print()
    print('2. In another terminal, get the login URL:')
    print('   python main.py test')
    print()
    print('3. Copy the login URL and open in your browser')
    print('4. Login to Zerodha and authorize the app')
    print('5. The access token will be saved automatically')
    print()
    print('⏰ This takes about 30-60 seconds')

def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'refresh':
        refresh_token()
        return

    # Check current token status
    is_valid = check_token_status()

    if is_valid:
        print()
        print('📅 TOKEN LIFECYCLE:')
        print('• ✅ Current token: VALID')
        print('• ⏰ Expires: In 24 hours or less')
        print('• 🔄 Next refresh: When API calls start failing')
        print('• 🤖 Auto-handling: Run this script to check status')
    else:
        print()
        print('💡 SOLUTION: Run token refresh')
        print('   python token_manager.py refresh')
        print('   (or follow the steps above)')

if __name__ == "__main__":
    main()