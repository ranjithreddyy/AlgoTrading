#!/bin/bash
# Setup script for MyAlgoTrader environment variables
# Run this script to set up your environment variables

echo "MyAlgoTrader Environment Setup"
echo "=============================="
echo ""

# Check if .env file exists
if [ -f ".env" ]; then
    echo "Found .env file. Loading environment variables..."
    # Export all variables from .env file
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue
        # Remove quotes from value if present
        value=$(echo "$value" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\(.*\)'$/\1/")
        export "$key=$value"
        echo "Exported: $key"
    done < .env
    echo "✅ Environment variables loaded successfully!"
    echo ""
    echo "To use in current session: source setup_env.sh"
    echo "To use in new sessions: add 'source $(pwd)/setup_env.sh' to your ~/.bashrc"
else
    echo "No .env file found. Creating one from template..."
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "Created .env file from template."
        echo "Please edit .env with your actual credentials."
        echo ""
        echo "Required variables:"
        echo "- KITE_API_KEY: Your Kite Connect API key"
        echo "- KITE_API_SECRET: Your Kite Connect API secret"
        echo "- KITE_USER_ID: Your Zerodha user ID (optional)"
        echo ""
        read -p "Do you want to edit .env now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-nano} .env
        fi
    else
        echo "Error: .env.example not found!"
        exit 1
    fi
fi

# Validate required variables
if [ -z "$KITE_API_KEY" ] || [ -z "$KITE_API_SECRET" ]; then
    echo "❌ Error: KITE_API_KEY and KITE_API_SECRET must be set!"
    echo "Please set them in your .env file or environment."
    exit 1
fi

echo ""
echo "Environment setup complete!"
echo "API Key: ${KITE_API_KEY:0:10}..."
echo "API Secret: ${KITE_API_SECRET:0:10}..."
if [ -n "$KITE_ACCESS_TOKEN" ]; then
    echo "Access Token: Set ✅"
else
    echo "Access Token: Not set (run login after setup)"
fi

echo ""
echo "You can now run:"
echo "python main.py test"
echo "python main.py backtest"