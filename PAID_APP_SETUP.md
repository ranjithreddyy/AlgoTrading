# Setting Up Paid Kite Connect App

## Step 1: Create Paid App on Zerodha Developer Console

1. Go to https://developers.kite.trade/apps
2. Click "Create a new app"
3. Select **Connect** type (₹500 for 30 days)
4. Fill in the details:

```
App name: PaidAlgoTest1
Zerodha Client ID: KFA715
Redirect URL: http://localhost:8000
Postback URL: https:// (leave empty)
Description: Algorithmic trading application with live market data
```

## Step 2: Update Environment Variables

After creating the paid app, you'll get new API credentials. Update your `.env` file:

```bash
# Replace with your PAID app credentials
KITE_API_KEY=wafpg35djb...  # Your paid app API key
KITE_API_SECRET=uhtcgwx8ux...  # Your paid app secret
KITE_USER_ID=your_user_id
KITE_ACCESS_TOKEN=  # Will be filled by OAuth flow
```

## Step 3: Authorize the App

```bash
# Start the OAuth callback server
python main.py oauth

# OR run directly
python oauth_callback_server.py
```

The server will start on http://localhost:8000

## Step 4: Get Login URL and Authorize

In a separate terminal:

```bash
python main.py test
```

This will show the login URL. Copy it, paste in browser, login, and authorize.

## Step 5: Verify Live Data Access

```bash
python main.py status
```

You should now see:
- ✅ Market status working
- ✅ Live price data available
- ✅ Full trading capabilities

## Features with Paid Plan

- ✅ Live market quotes and ticks
- ✅ Historical chart data APIs
- ✅ WebSocket streaming
- ✅ All investing/trading/report APIs

## Troubleshooting

- **Port 8000 busy**: Use `python oauth_callback_server.py 8080` for port 8080
- **Access token not saved**: Check that `.env` file is writable
- **Still no market data**: Ensure you're using the paid app credentials