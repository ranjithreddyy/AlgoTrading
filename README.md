# MyAlgoTrader

Algorithmic trading application using Zerodha Kite Connect API.

## Features

- Connect to Zerodha Kite Connect API
- Backtest trading strategies
- Live trading (planned)
- Real-time data streaming (planned)

## Setup

1. Create a Kite Connect app at https://developers.kite.trade/apps
2. Update `src/config.py` with your API key and secret
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
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