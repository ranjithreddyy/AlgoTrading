#!/usr/bin/env python3
"""
HTTPS OAuth Callback Server for Kite Connect
Provides secure HTTPS callback for local development
"""

import ssl
import http.server
import socketserver
import urllib.parse
import json
import os
import sys
from kiteconnect import KiteConnect

class HTTPSOAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        """Handle GET request (OAuth callback)"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        # Parse the URL to extract parameters
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)

        print(f"🔒 HTTPS Request received: {self.path}")
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
                <head>
                    <style>
                        body {{
                            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                            text-align: center;
                            padding: 50px;
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                            color: white;
                            margin: 0;
                        }}
                        .container {{
                            background: rgba(255, 255, 255, 0.1);
                            border-radius: 10px;
                            padding: 30px;
                            box-shadow: 0 8px 32px rgba(31, 38, 135, 0.37);
                            backdrop-filter: blur(4px);
                            border: 1px solid rgba(255, 255, 255, 0.18);
                        }}
                        h1 {{ color: #4CAF50; margin-bottom: 20px; }}
                        .token {{
                            background: rgba(0, 0, 0, 0.2);
                            padding: 10px;
                            border-radius: 5px;
                            font-family: monospace;
                            word-break: break-all;
                        }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🔐 Authorization Successful!</h1>
                        <p>Your Kite Connect app has been authorized securely via HTTPS.</p>
                        <p>Access token saved to .env file.</p>
                        <p>You can now close this window and return to your terminal.</p>
                        <hr>
                        <p><strong>Access Token:</strong></p>
                        <div class="token">{access_token[:20]}...</div>
                    </div>
                </body>
                </html>
                """

                self.wfile.write(success_html.encode())

            except Exception as e:
                error_html = f"""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5;">
                    <h1 style="color: red;">❌ Authorization Failed</h1>
                    <p>Error: {str(e)}</p>
                    <p>Please check your API credentials and try again.</p>
                    <p>Make sure your .env file has the correct KITE_API_KEY and KITE_API_SECRET</p>
                </body>
                </html>
                """
                self.wfile.write(error_html.encode())
                print(f"❌ Error generating access token: {e}")

        else:
            error_html = """
            <html>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5;">
                <h1 style="color: red;">❌ No Request Token</h1>
                <p>No request_token parameter found in the URL.</p>
                <p>Please try the authorization process again.</p>
                <hr>
                <p><strong>Debug Info:</strong></p>
                <p>Path: {self.path}</p>
                <p>Query: {parsed_path.query}</p>
                <p>Params: {query_params}</p>
                <hr>
                <p><em>This is a secure HTTPS connection for local development.</em></p>
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

def run_https_server(port=8443):
    """Run the HTTPS OAuth callback server"""
    server_address = ('', port)

    # Check if certificates exist
    if not os.path.exists('cert.pem') or not os.path.exists('key.pem'):
        print("❌ SSL certificates not found. Run certificate generation first:")
        print("python -c \"import subprocess; subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:4096', '-keyout', 'key.pem', '-out', 'cert.pem', '-days', '365', '-nodes', '-subj', '/C=IN/ST=State/L=City/O=Organization/CN=localhost'], check=True)\"")
        return

    httpd = http.server.HTTPServer(server_address, HTTPSOAuthCallbackHandler)

    # Wrap the socket with SSL
    httpd.socket = ssl.wrap_socket(httpd.socket,
                                   keyfile="key.pem",
                                   certfile="cert.pem",
                                   server_side=True)

    print("🔒 SECURE HTTPS OAuth callback server running!")
    print(f"🌐 URL: https://localhost:{port}")
    print("🔑 This provides secure HTTPS for local development")
    print("📋 Use this URL in your Kite Connect app: https://localhost:8443")
    print("⚠️  Browser will show security warning - click 'Advanced' -> 'Proceed to localhost'")
    print("Waiting for authorization callback...")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.shutdown()

if __name__ == "__main__":
    port = 8443
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("❌ Invalid port number")
            sys.exit(1)

    run_https_server(port)