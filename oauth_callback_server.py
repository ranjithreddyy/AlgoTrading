#!/usr/bin/env python3
"""
OAuth Callback Server for Kite Connect
Handles the redirect from Zerodha after authorization
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import json
import os
import sys
import socket
import subprocess
from kiteconnect import KiteConnect

def get_wsl_ip():
    """Get WSL IP address for Windows browser access"""
    try:
        # Method 1: Get IP from eth0 interface
        try:
            result = subprocess.run(['ip', 'addr', 'show', 'eth0'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and not line.strip().startswith('127.'):
                        ip = line.strip().split()[1].split('/')[0]
                        if not ip.startswith('127.'):
                            return ip
        except:
            pass

        # Method 2: Try hostname resolution
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if not ip.startswith('127.'):
            return ip

        # Method 3: Check all interfaces
        try:
            result = subprocess.run(['ip', 'addr', 'show'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line and 'eth0' in line and not '127.' in line:
                        ip = line.strip().split()[1].split('/')[0]
                        return ip
        except:
            pass

        # Method 4: Use hostname command
        try:
            result = subprocess.run(['hostname', '-I'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ips = result.stdout.strip().split()
                for ip in ips:
                    if not ip.startswith('127.'):
                        return ip
        except:
            pass

        return '0.0.0.0'
    except:
        return '0.0.0.0'

def is_wsl():
    """Check if running in WSL"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET request (OAuth callback)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Parse the URL to extract parameters
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        print(f"📡 Received request: {self.path}")
        print(f"🔍 Query params: {list(query_params.keys())}")

        if 'request_token' in query_params:
            request_token = query_params['request_token'][0]
            print(f"✅ Received request_token: {request_token}")

            # Generate access token
            try:
                API_KEY = os.getenv('KITE_API_KEY')
                API_SECRET = os.getenv('KITE_API_SECRET')

                if not API_KEY or not API_SECRET:
                    error_msg = "❌ Environment variables not set"
                    self.wfile.write(error_msg.encode())
                    return

                kite = KiteConnect(api_key=API_KEY)
                data = kite.generate_session(request_token, api_secret=API_SECRET)

                access_token = data['access_token']
                print(f"✅ Generated access token: {access_token}")

                # Save to environment file
                env_file = '.env'
                if os.path.exists(env_file):
                    with open(env_file, 'r') as f:
                        lines = f.readlines()
                else:
                    lines = []

                # Update or add ACCESS_TOKEN
                token_found = False
                for i, line in enumerate(lines):
                    if line.startswith('KITE_ACCESS_TOKEN='):
                        lines[i] = f'KITE_ACCESS_TOKEN={access_token}\n'
                        token_found = True
                        break

                if not token_found:
                    lines.append(f'KITE_ACCESS_TOKEN={access_token}\n')

                with open(env_file, 'w') as f:
                    f.writelines(lines)

                print(f"✅ Access token saved to {env_file}")

                success_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ Authorization Successful!</h1>
                    <p>Your Kite Connect app has been authorized.</p>
                    <p>Access token saved to .env file.</p>
                    <p>You can now close this window and return to your terminal.</p>
                    <hr>
                    <p><strong>Access Token:</strong> {access_token[:20]}...</p>
                </body>
                </html>
                """

                self.wfile.write(success_html.encode())

            except Exception as e:
                error_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: red;">❌ Authorization Failed</h1>
                    <p>Error: {str(e)}</p>
                    <p>Please check your API credentials and try again.</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                print(f"❌ Error generating access token: {e}")

        else:
            error_html = """
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">❌ No Request Token</h1>
                <p>No request_token parameter found in the URL.</p>
                <p>Please try the authorization process again.</p>
                <hr>
                <p><strong>Debug Info:</strong></p>
                <p>Path: {self.path}</p>
                <p>Query: {parsed_path.query}</p>
                <p>Params: {query_params}</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
            print("❌ No request_token in URL")
            print(f"   Path: {self.path}")
            print(f"   Query: {parsed_path.query}")

    def log_message(self, format, *args):
        """Suppress default HTTP server logs"""
        return

def run_server(port=8000):
    """Run the OAuth callback server"""
    wsl_mode = is_wsl()
    if wsl_mode:
        # In WSL, bind to all interfaces and get WSL IP
        server_address = ('0.0.0.0', port)
        wsl_ip = get_wsl_ip()
        print(f"🐧 WSL detected! Server will be accessible from Windows browser")
        print(f"🌐 WSL IP Address: {wsl_ip}")
        print(f"🔗 Use this URL in Zerodha app settings: http://{wsl_ip}:{port}")
        print(f"💡 Or use: http://localhost:{port} (if port forwarding is set up)")
    else:
        server_address = ('', port)
        print(f"🖥️  Local server running on http://localhost:{port}")

    httpd = HTTPServer(server_address, OAuthCallbackHandler)
    print(f"🚀 OAuth callback server running on port {port}")
    print("Waiting for authorization callback...")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.shutdown()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid port number")
            sys.exit(1)

    run_server(port)