#!/usr/bin/env python3

from kiteconnect import KiteConnect
from dotenv import load_dotenv
import urllib.parse
import os
import sys

load_dotenv()

# Your API credentials from environment variables
API_KEY = os.getenv('KITE_API_KEY')
API_SECRET = os.getenv('KITE_API_SECRET')
REDIRECT_URI = os.getenv('REDIRECTURL', 'http://127.0.0.1:5000/')

# Validate that environment variables are set
if not API_KEY or not API_SECRET:
    print("❌ Error: Please set KITE_API_KEY and KITE_API_SECRET environment variables")
    print("Example:")
    print("export KITE_API_KEY='your_api_key'")
    print("export KITE_API_SECRET='your_api_secret'")
    exit(1)

def main():
    # Check if URL is provided as command line argument
    if len(sys.argv) > 1:
        redirected_url = sys.argv[1]
        print(f"Using provided URL: {redirected_url}")
    else:
        # Initialize KiteConnect
        kite = KiteConnect(api_key=API_KEY)

        # Get login URL
        login_url = kite.login_url()
        print("🔗 LOGIN URL (Copy and paste this in your browser):")
        print(login_url)
        print("\n" + "="*80)

        # Check if WSL and provide appropriate instructions
        try:
            with open('/proc/version', 'r') as f:
                is_wsl = 'microsoft' in f.read().lower()
        except:
            is_wsl = False

        if is_wsl:
            print("🐧 WSL DETECTED - Special instructions for Windows browser:")
            print("1. The server will show your WSL IP address")
            print("2. Make sure your Kite app redirect URL uses that IP")
            print("3. Use Windows Chrome/Edge browser (not WSL browser)")
            print("4. Run: python wsl_helper.py (to see your IP)")
        else:
            print("INSTRUCTIONS:")

        print("1. Start OAuth server: python main.py oauth")
        print("2. Copy the URL above and paste it in your browser")
        print("3. Login to Zerodha and authorize the app")
        print("4. You will be redirected automatically")
        print("5. Access token will be saved to your .env file")
        print("="*80)
        return

    # Extract request_token from the URL
    parsed_url = urllib.parse.urlparse(redirected_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)

    if 'request_token' not in query_params:
        print("❌ Error: No request_token found in the URL")
        print("Make sure you copied the complete redirected URL")
        return

    request_token = query_params['request_token'][0]
    print(f"✅ Request token extracted: {request_token[:10]}...")

    # Initialize KiteConnect
    kite = KiteConnect(api_key=API_KEY)

    # Generate session
    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        kite.set_access_token(data["access_token"])
        print("🎉 Access token obtained successfully!")
        print(f"Access Token: {data['access_token']}")
        print("\n💡 Add this to your .env file:")
        print(f"KITE_ACCESS_TOKEN={data['access_token']}")

        # Test the connection
        profile = kite.profile()
        print("\n✅ Connection successful! User profile:")
        print(f"User ID: {profile['user_id']}")
        print(f"Email: {profile['email']}")
        print(f"User name: {profile['user_name']}")

    except Exception as e:
        print(f"❌ Error generating session: {e}")

if __name__ == "__main__":
    main()