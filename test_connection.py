#!/usr/bin/env python3

from kiteconnect import KiteConnect
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import threading
import time
import os

# Your API credentials from environment variables
API_KEY = os.getenv('KITE_API_KEY')
API_SECRET = os.getenv('KITE_API_SECRET')
REDIRECT_URI = "http://localhost:8000"

# Validate that environment variables are set
if not API_KEY or not API_SECRET:
    print("Error: Please set KITE_API_KEY and KITE_API_SECRET environment variables")
    print("Example:")
    print("export KITE_API_KEY='your_api_key'")
    print("export KITE_API_SECRET='your_api_secret'")
    exit(1)

# Global variable to store request token
request_token = None

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global request_token
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        if 'request_token' in query_params:
            request_token = query_params['request_token'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Login successful! You can close this window.</h1></body></html>")
            print("Request token received:", request_token)
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Error: No request token</h1></body></html>")

    def log_message(self, format, *args):
        # Suppress server logs
        pass

def start_server():
    server = HTTPServer(('localhost', 8000), RequestHandler)
    print("Starting local server on http://localhost:8000")
    server.serve_forever()

def main():
    # Initialize KiteConnect
    kite = KiteConnect(api_key=API_KEY)

    # Get login URL
    login_url = kite.login_url()
    print("Login URL:", login_url)

    # Open browser automatically
    webbrowser.open(login_url)

    # Start server in a separate thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Wait for request token
    print("Waiting for you to login and authorize...")
    while request_token is None:
        time.sleep(1)

    # Generate session
    try:
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        kite.set_access_token(data["access_token"])
        print("Access token obtained successfully!")

        # Test the connection
        profile = kite.profile()
        print("Connection successful! User profile:")
        print(f"User ID: {profile['user_id']}")
        print(f"Email: {profile['email']}")
        print(f"User name: {profile['user_name']}")

    except Exception as e:
        print(f"Error generating session: {e}")

if __name__ == "__main__":
    main()