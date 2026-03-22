#!/usr/bin/env python3
"""
WSL Networking Helper for Kite Connect OAuth
Helps configure the correct redirect URL for WSL environments
"""

import socket
import subprocess
import os

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

        return None
    except:
        return None

def is_wsl():
    """Check if running in WSL"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False

def main():
    print("🐧 WSL Networking Helper for Kite Connect")
    print("=" * 50)

    if not is_wsl():
        print("❌ Not running in WSL environment")
        print("This helper is only needed for WSL users")
        return

    print("✅ WSL environment detected")

    wsl_ip = get_wsl_ip()
    if wsl_ip:
        print(f"🌐 Your WSL IP Address: {wsl_ip}")
        print()
        print("📋 For your Kite Connect app, use this redirect URL:")
        print(f"   http://{wsl_ip}:8000")
        print()
        print("🔧 Steps to complete setup:")
        print("1. Go to https://developers.kite.trade/apps")
        print("2. Edit your PaidAlgoTest1 app")
        print("3. Change Redirect URL to:")
        print(f"   http://{wsl_ip}:8000")
        print("4. Save the app")
        print("5. Run: python main.py oauth")
        print("6. Use Windows browser to authorize")
    else:
        print("❌ Could not determine WSL IP address")
        print()
        print("🔧 Troubleshooting:")
        print("1. Run: ip addr show")
        print("2. Look for eth0 interface IP (not 127.0.0.1)")
        print("3. Use that IP in the redirect URL")
        print()
        print("💡 Alternative: Set up Windows port forwarding")
        print("   In Windows PowerShell (as Administrator):")
        print("   netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=127.0.0.1")

if __name__ == "__main__":
    main()