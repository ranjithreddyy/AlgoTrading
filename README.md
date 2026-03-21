# MyAlgoTrader

Algorithmic trading application using Zerodha Kite Connect API.

## Features

- Connect to Zerodha Kite Connect API
- Backtest trading strategies
- Live trading (planned)
- Real-time data streaming (planned)

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ranjithreddyy/AlgoTrading.git
   cd AlgoTrading
   ```

2. Create a Kite Connect app at https://developers.kite.trade/apps

3. Set environment variables for your API credentials:
   ```bash
   export KITE_API_KEY="your_api_key_from_kite_app"
   export KITE_API_SECRET="your_api_secret_from_kite_app"
   export KITE_USER_ID="your_zerodha_user_id"  # Optional
   ```

   For persistent environment variables, add them to your `~/.bashrc` or `~/.zshrc`:
   ```bash
   echo 'export KITE_API_KEY="your_api_key"' >> ~/.bashrc
   echo 'export KITE_API_SECRET="your_api_secret"' >> ~/.bashrc
   source ~/.bashrc
   ```

4. Copy the config template and ensure it uses environment variables:
   ```bash
   cp src/config_template.py src/config.py
   ```
   The `src/config.py` will automatically read from environment variables.

5. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

6. Test the connection:
   ```bash
   python test_connection.py
   ```
   Follow the login URL to authorize the app. After successful login, set the access token:
   ```bash
   export KITE_ACCESS_TOKEN="access_token_from_login"
   ```

## Usage

### Test Connection
```bash
python main.py test
```

### Run Backtest
```bash
python main.py backtest --strategy sma
```

### Live Trading (Not implemented yet)
```bash
python main.py live
```

## Project Structure

```
MyAlgoTrader/
├── src/
│   ├── config.py          # API configuration
│   └── kite_client.py     # Kite Connect client wrapper
├── strategies/
│   └── sma_strategy.py    # Simple moving average strategy
├── backtests/
│   └── run_backtest.py    # Backtesting framework
├── data/                  # Historical data storage
├── main.py                # Main application entry point
└── requirements.txt       # Python dependencies
```

## Strategies

### Simple Moving Average (SMA)
A basic crossover strategy using fast and slow moving averages.

## Backtesting

Uses Backtrader framework for backtesting strategies on historical data.

## Live Trading

Planned features:
- Real-time order execution
- Risk management
- Position monitoring
- WebSocket data streaming

## Security

- Never commit API secrets to version control
- Use environment variables for sensitive data in production
- Keep access tokens secure and rotate regularly

## License

MIT License