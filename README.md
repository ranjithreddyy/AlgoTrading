# MyAlgoTrader

Algorithmic trading platform using Zerodha Kite Connect API for Indian intraday trading.

## Setup

1. Clone and install:
   ```bash
   git clone <repo-url>
   cd TradingZeroda
   python3 -m venv .venv --without-pip
   curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python3
   .venv/bin/pip install -r requirements.txt python-dotenv
   ```

2. Configure `.env` with your Kite API credentials:
   ```
   KITE_API_KEY=your_api_key
   KITE_API_SECRET=your_api_secret
   KITE_USER_ID=your_user_id
   KITE_ACCESS_TOKEN=
   REDIRECTURL=http://127.0.0.1:5000/
   ```

3. Authenticate and get access token:
   ```bash
   .venv/bin/python test_connection.py
   # Open login URL in browser, authorize, copy redirected URL
   .venv/bin/python test_connection.py "PASTE_REDIRECTED_URL"
   # Update KITE_ACCESS_TOKEN in .env
   ```

---

## Key Commands

```bash
# Run all strategies on a stock
.venv/bin/python scripts/run_backtests.py --all --symbol RELIANCE --interval day
.venv/bin/python scripts/run_backtests.py --all --symbol NIFTY_50 --interval day --exchange INDEX

# Run parameter sweep
.venv/bin/python scripts/run_backtests.py --all --symbol RELIANCE --interval day --sweep

# Generate HTML tournament report
.venv/bin/python scripts/run_tournament.py --symbol RELIANCE --interval day

# Run all tests
.venv/bin/python -m pytest tests/ -v

# Ingest historical data
.venv/bin/python scripts/ingest_history.py --symbol RELIANCE --interval day --days 730

# Train models
.venv/bin/python scripts/train_models.py --symbol RELIANCE --interval day

# Run paper trading
.venv/bin/python scripts/run_paper_trading.py

# Sync instrument master
.venv/bin/python scripts/sync_instruments.py
```

---

## Project Structure

```
src/
├── backtests/
│   ├── batch_runner.py        # Parallel strategy execution via ProcessPoolExecutor
│   ├── costs.py               # Full Indian cost model (STT, GST, SEBI, stamp duty)
│   ├── engine.py              # Bar-by-bar event simulation engine
│   ├── execution_quality.py   # Fill quality analytics
│   └── reports.py             # HTML equity curve comparison reports
├── broker/
│   ├── base.py                # Abstract broker interface
│   ├── execution_router.py    # Live/paper routing logic
│   ├── kite_broker.py         # Zerodha Kite live broker
│   └── paper_broker.py        # Simulated fills with spread/slippage
├── config/
│   └── settings.py            # Centralized settings (pydantic)
├── core/
│   ├── calendar.py            # NSE holiday calendar, F&O expiry detection
│   ├── clock.py               # Market clock / session timing
│   ├── enums.py               # Shared enumerations
│   ├── logger.py              # Structured logging framework
│   └── types.py               # Pydantic data models
├── data/
│   ├── historical_loader.py   # Load CSV bars into DataFrames
│   ├── ingestion.py           # Backfill engine with rate limiting
│   ├── quality.py             # OHLCV validation and quality checks
│   ├── storage.py             # CSV store with dedup / merge on save
│   ├── tick_aggregator.py     # Tick-to-bar aggregation
│   └── websocket_feed.py      # WebSocket feed with reconnect
├── features/
│   ├── compute.py             # compute_features() convenience function
│   ├── cross_asset.py         # Correlation, beta, dispersion features
│   ├── feature_registry.py    # Feature registry
│   ├── market_context.py      # NIFTY return, VIX, breadth features
│   ├── mean_reversion_features.py  # RSI, Connors RSI, Bollinger z-score
│   ├── options_features.py    # Options-specific features
│   ├── price_features.py      # Returns, EMA, SMA, ADX, VWAP, Donchian
│   ├── regime_features.py     # Hurst exponent, vol regime, half-life
│   ├── volatility_features.py # ATR, Parkinson, Garman-Klass
│   └── volume_features.py     # Relative volume, OBV, CMF, volume momentum
├── instruments/
│   ├── corporate_actions.py   # Splits, bonuses, ex-dividend tracking
│   ├── greeks.py              # Delta, gamma, theta, vega, IV calculation
│   ├── instrument_master.py   # Daily download & archive (NSE + NFO)
│   ├── option_chain.py        # Nearest weekly ATM ± strikes
│   └── symbol_resolver.py     # Symbol → instrument token lookup
├── labels/
│   ├── horizon_returns.py     # Fixed-horizon forward returns
│   ├── meta_labels.py         # Meta-labels for execution filtering
│   └── triple_barrier.py      # Triple-barrier labeling
├── live/
│   ├── alerts.py              # Telegram/webhook alert dispatch
│   ├── crash_recovery.py      # State persistence and recovery
│   ├── health_check.py        # System health monitoring
│   ├── monitoring.py          # Runtime monitoring
│   ├── session_manager.py     # Trading session lifecycle
│   ├── signal_service.py      # Strategy signal aggregation
│   ├── token_refresh.py       # Kite token refresh automation
│   └── trade_loop.py          # Main live trading loop
├── models/
│   ├── baselines.py           # LogReg, RF baseline models
│   ├── inference.py           # Model inference wrapper
│   ├── model_registry.py      # Versioned model storage
│   └── tree_models.py         # CatBoost / LightGBM / XGBoost wrappers
├── research/
│   ├── evaluate.py            # Strategy evaluation framework
│   ├── feature_selection.py   # Feature importance & selection
│   ├── optimize.py            # Parameter optimization
│   ├── selection.py           # Strategy tournament / selection
│   ├── train.py               # Training pipeline
│   └── walk_forward.py        # Walk-forward splits with purging & embargo
├── risk/
│   ├── kill_switch.py         # Manual + automated kill switch
│   ├── limits.py              # Daily loss / trades / consecutive loss limits
│   └── sizing.py              # Position sizing (Kelly, fixed-fraction)
└── strategies/
    ├── base.py                # Common Strategy interface / StrategyConfig
    ├── gamma_scalp.py         # Strategy I: Expiry-Day Gamma Scalp
    ├── mean_reversion.py      # Strategy B: RSI Mean Reversion
    ├── momentum_breakout.py   # Strategy A: Momentum Breakout
    ├── option_fade.py         # Strategy D: NIFTY Option Range Fade
    ├── option_momentum.py     # Strategy C: NIFTY Option Momentum
    ├── orb_strategy.py        # Strategy E: Opening Range Breakout
    ├── registry.py            # StrategyRegistry with auto-discovery
    ├── straddle_breakout.py   # Strategy H: Straddle Breakout
    ├── volume_spike.py        # Strategy G: Volume Spike Momentum
    └── vwap_reversion.py      # Strategy F: VWAP Reversion
```

---

## Implementation Progress

### Stage 0: Repo Stabilization & Capability Probe

- [x] **Environment & Config**
	- [x] `.env` file with API credentials
	- [x] `python-dotenv` auto-loading in scripts
	- [x] Remove hardcoded machine-specific paths
	- [x] Fix `main.py` command routing (broken refs: `run_backtest`, `start_oauth_server`)
	- [x] Make config/auth checks runtime-bound (not import-time crashes)
	- [ ] Separate manual broker scripts from automated test discovery

- [x] **API Access Verified**
	- [x] Kite Connect authentication working
	- [x] Profile fetch working
	- [x] NSE instruments fetch (9,517 instruments)
	- [x] NFO instruments fetch (50,863 instruments)
	- [x] Historical day candles (2+ years depth)
	- [x] Historical minute candles working
	- [x] Historical 5min/15min interval verified (NIFTY 50 downloaded)
	- [ ] OI (open interest) support test for NFO
	- [ ] Expired instrument behavior test

- [ ] **Historical Capability Probe (Phase 0.5)**
	- [x] Test NIFTY index historical data (day + 15min + 5min downloaded)
	- [ ] Build probe script for systematic interval/depth testing
	- [ ] Test all intervals: minute, 3minute
	- [ ] Find earliest reachable date per interval
	- [ ] Test OI data for derivatives
	- [ ] Test NIFTY option historical data
	- [ ] Generate probe report (CSV/JSON)

### Milestone 1: Foundation

- [x] **Project Structure**
	- [x] Create `src/` module layout per architecture plan
	- [x] Set up logging framework (`src/core/logger.py`)
	- [x] Add `pydantic` data models (`src/core/types.py`)
	- [x] Core enums (`src/core/enums.py`)
	- [x] Market clock (`src/core/clock.py`)
	- [x] Centralized settings (`src/config/settings.py`)

- [x] **Instrument Master**
	- [x] Daily instrument master download & archive (`src/instruments/instrument_master.py`)
	- [x] CSV storage: `data/raw/instruments/YYYY-MM-DD/` (NSE + NFO)
	- [x] Symbol resolution utilities (`src/instruments/symbol_resolver.py`)
	- [x] Option chain selection - nearest weekly, ATM +/- strikes (`src/instruments/option_chain.py`)
	- [x] Sync script (`scripts/sync_instruments.py`)

- [x] **NSE Trading Calendar**
	- [x] Holiday calendar awareness (2025 + 2026 holidays)
	- [x] Market session timing (pre-market, regular, closing)
	- [x] F&O expiry day detection (weekly + monthly)
	- [ ] Special session handling (Muhurat, early close)

- [x] **Corporate Actions**
	- [x] Track splits, bonuses, ex-dividend dates (`src/instruments/corporate_actions.py`)
	- [ ] Adjust historical data for corporate actions
	- [ ] Flag symbols under corporate action

- [x] **Historical Data Ingestion**
	- [x] Backfill engine with date-range support (`src/data/ingestion.py`)
	- [x] Dedup logic (`src/data/storage.py` - merge on save)
	- [x] Rate limiting (0.35s between calls)
	- [x] Data quality validation (`src/data/quality.py`)
	- [x] CSV storage: `data/market/{exchange}/{symbol}/{interval}/`
	- [x] CLI ingestion script (`scripts/ingest_history.py`)
	- [ ] Parquet storage migration (currently CSV)

- [ ] **Storage Layer**
	- [x] CSV-based local storage with load/save/query
	- [ ] Parquet + DuckDB migration
	- [ ] Snappy/Zstd compression
	- [ ] SQLite trade log schema
	- [ ] Data retention policy enforcement

- [x] **Tests** (86/86 passing in 0.95s)
	- [x] Core module tests (enums, clock, calendar) - 8 tests
	- [x] Cost model tests - 6 tests
	- [x] Data tests (storage, quality validation, fix) - 7 tests
	- [x] Feature tests - 7 tests
	- [x] Instrument tests (master, tokens, search, option chain) - 6 tests
	- [x] Label tests (horizon returns, triple barrier, meta labels) - 4 tests
	- [x] Portfolio tests - 31 tests
	- [x] Risk tests (sizing, limits, kill switch) - 5 tests
	- [x] Strategy tests (config, registry, engine, batch runner, sweep) - 8 tests
	- [x] Walk-forward tests - 4 tests

### Milestone 2: Research Pipeline

- [x] **Feature Library** (44+ features across 10 modules)
	- [x] Price & trend features (returns, EMA, SMA, ADX, VWAP, Donchian, trend slope)
	- [x] Mean reversion features (RSI, Connors RSI, Bollinger z-score, VWAP deviation)
	- [x] Volatility features (ATR, Parkinson, Garman-Klass, bar range score)
	- [x] Volume features (relative volume, OBV, CMF, volume momentum)
	- [x] Options features (`src/features/options_features.py`)
	- [x] Market context features (`src/features/market_context.py` - NIFTY return, VIX, breadth)
	- [x] Cross-asset features (`src/features/cross_asset.py` - correlation, beta, dispersion)
	- [x] Regime detection features (Hurst exponent, vol regime, trend strength, half-life)
	- [x] Feature registry with compute_features() convenience function
	- [ ] Microstructure features (spread, depth imbalance) - needs tick data

- [x] **Labels**
	- [x] Fixed-horizon forward returns (`src/labels/horizon_returns.py`)
	- [x] Triple-barrier labels (`src/labels/triple_barrier.py`)
	- [x] Meta-labels for execution filtering (`src/labels/meta_labels.py`)

- [x] **Training Pipeline**
	- [x] Walk-forward split with purging & embargo (`src/research/walk_forward.py`)
	- [x] Strategy evaluation framework (`src/research/evaluate.py`)
	- [x] Strategy tournament / selection (`src/research/selection.py`)
	- [x] Baseline models: LogReg, RF (`src/models/baselines.py`)
	- [x] Tree models: CatBoost/LightGBM/XGBoost wrappers (`src/models/tree_models.py`)
	- [x] Model registry & versioning (`src/models/model_registry.py`, artifacts saved)
	- [x] Model inference wrapper (`src/models/inference.py`)
	- [x] Feature selection (`src/research/feature_selection.py`)
	- [ ] SHAP / feature importance tracking
	- [ ] Model measurement (post-cost PnL, Sharpe, drawdown)

- [x] **Backtesting Engine**
	- [x] Bar-by-bar event simulation (`src/backtests/engine.py`)
	- [x] Full Indian cost model - STT, GST, SEBI, stamp duty (`src/backtests/costs.py`)
	- [x] Stop-loss and target handling
	- [x] HTML comparison reports with equity curves (`src/backtests/reports.py`)
	- [x] Execution quality analytics (`src/backtests/execution_quality.py`)
	- [ ] Partial/rejected/missed fills
	- [ ] Survivorship-bias-free universe

- [x] **Multi-Strategy Parallel Testing**
	- [x] Common `Strategy` interface / base class (`src/strategies/base.py`)
	- [x] `StrategyRegistry` with auto-discovery (`src/strategies/registry.py`)
	- [x] `BatchRunner` for parallel execution via ProcessPoolExecutor (`src/backtests/batch_runner.py`)
	- [x] Parameter grid / sweep support per strategy
	- [ ] Optuna hyperparameter search integration
	- [x] Ranked leaderboard (PnL, Sharpe, profit factor, drawdown, win rate)
	- [x] Equity curve comparison in HTML report
	- [ ] Strategy return correlation matrix
	- [x] HTML tournament report (`scripts/run_tournament.py`)
	- [x] `scripts/run_backtests.py --all` entry point (verified working)
	- [x] Walk-forward tournament across all strategies

- [x] **Stock Strategies** (9 strategies auto-discovered, tested on 7 symbols)
	- [x] Strategy A: Momentum Breakout (`src/strategies/momentum_breakout.py`)
	- [x] Strategy B: Mean Reversion (`src/strategies/mean_reversion.py`)
	- [x] Strategy E: Opening Range Breakout (`src/strategies/orb_strategy.py`)
	- [x] Strategy F: VWAP Reversion (`src/strategies/vwap_reversion.py`)
	- [x] Strategy G: Volume Spike Momentum (`src/strategies/volume_spike.py`)

### Milestone 3: Option Research

- [x] **Option Chain**
	- [x] Option chain resolver (`src/instruments/option_chain.py`)
	- [x] Greeks calculation (delta, gamma, theta, vega, IV) (`src/instruments/greeks.py`)
	- [x] Options features & labels (`src/features/options_features.py`)
	- [ ] Expiry-day special risk rules

- [x] **Option Strategies** (all implemented and tested on NIFTY 50)
	- [x] Strategy C: NIFTY Option Momentum (`src/strategies/option_momentum.py`)
	- [x] Strategy D: NIFTY Option Range Fade (`src/strategies/option_fade.py`)
	- [x] Strategy H: Straddle Breakout (`src/strategies/straddle_breakout.py`)
	- [x] Strategy I: Expiry-Day Gamma Scalp (`src/strategies/gamma_scalp.py`)
	- [ ] Cross-strategy correlation & diversification analysis
	- [ ] Multi-strategy portfolio-level Sharpe optimization

### Milestone 4: Paper Trading

- [x] **Live Data**
	- [x] WebSocket feed with reconnect & resilience (`src/data/websocket_feed.py`)
	- [x] Intraday tick aggregation (`src/data/tick_aggregator.py`)
	- [x] Stream health monitoring (`src/live/health_check.py`)

- [x] **Paper Broker**
	- [x] Simulated fills with spread/slippage (`src/broker/paper_broker.py`)
	- [x] Execution router for live/paper routing (`src/broker/execution_router.py`)
	- [ ] Full trade ledger with daily report generation
	- [ ] PnL tracking by strategy family

- [x] **Risk Engine**
	- [x] Daily max loss / max trades / consecutive loss limits (`src/risk/limits.py`)
	- [x] Per-trade capital & stop-loss enforcement
	- [x] Position sizing (Kelly, fixed-fraction) (`src/risk/sizing.py`)
	- [x] Kill switch (manual + automated) (`src/risk/kill_switch.py`)
	- [x] Crash recovery & state persistence (`src/live/crash_recovery.py`)
	- [ ] Time rules (no trade near open/close)
	- [ ] Circuit breaker detection

### Milestone 5: Live Readiness

- [x] **Execution**
	- [x] Execution router & reconciler (`src/broker/execution_router.py`)
	- [x] Kill switch (manual + automated) (`src/risk/kill_switch.py`)
	- [x] Token refresh automation (`src/live/token_refresh.py`)

- [x] **Monitoring**
	- [x] Telegram/webhook alerts (`src/live/alerts.py`)
	- [x] Execution quality analytics (`src/backtests/execution_quality.py`)
	- [x] Session manager and trade loop (`src/live/session_manager.py`, `src/live/trade_loop.py`)
	- [ ] Paper vs live drift tracking

- [ ] **Rollout**
	- [ ] Shadow mode (signals only, no orders)
	- [ ] Micro-live (1 strategy, small universe, strict cap)
	- [ ] Controlled scale-up

---

## Data Downloaded

| Dataset | Interval | Date Range | Records | Status |
|---------|----------|------------|---------|--------|
| NSE Instruments | - | 2026-03-22 | 9,517 | Done |
| NFO Instruments | - | 2026-03-22 | 50,863 | Done |
| NIFTY 50 | day | 2024-03-22 to 2026-03-22 | 495 | Done |
| NIFTY 50 | 15min | 2025-09-03 to 2026-03-22 | 3,379 | Done |
| NIFTY 50 | 5min | 2025-12-12 to 2026-03-22 | 4,950 | Done |
| RELIANCE | day | 2024-03-22 to 2026-03-22 | 495 | Done |
| RELIANCE | 15min | 2025-09-03 to 2026-03-22 | 3,379 | Done |
| TCS | day | 2024-03-22 to 2026-03-22 | 495 | Done |
| TCS | 15min | 2025-09-03 to 2026-03-22 | 3,379 | Done |
| HDFCBANK | day + 15min | 2yr + 6mo | 3,874 | Done |
| INFY | day + 15min | 2yr + 6mo | 3,874 | Done |
| ICICIBANK | day + 15min | 2yr + 6mo | 3,874 | Done |
| SBIN | day + 15min | 2yr + 6mo | 3,874 | Done |
| HINDUNILVR | day + 15min | 2yr + 6mo | 3,874 | Done |
| BHARTIARTL | day + 15min | 2yr + 6mo | 3,874 | Done |
| KOTAKBANK | day + 15min | 2yr + 6mo | 3,874 | Done |
| LT | day + 15min | 2yr + 6mo | 3,874 | Done |

*(Updated as data is ingested)*

---

## Latest Backtest Results

All results use 2 years of daily data (495 bars, 2024-03-22 to 2026-03-22). PnL is in points/rupees per 1-lot equivalent. 9 strategies auto-discovered and run in parallel.

### RELIANCE (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | VWAP Reversion | 21 | 71.4% | +476.83 | 2.02 | 4.39 | 48.19 |
| 2 | Volume Spike | 15 | 53.3% | +255.44 | 1.04 | 2.33 | 63.06 |
| 3 | Momentum Breakout | 16 | 50.0% | +182.20 | 0.76 | 1.76 | 156.69 |
| 4 | Mean Reversion | 27 | 48.1% | +154.51 | 0.54 | 1.36 | 149.65 |
| 5 | Option Fade | 30 | 46.7% | +96.64 | 0.45 | 1.26 | 70.33 |
| 6 | Straddle Breakout | 17 | 35.3% | -17.44 | -0.10 | 0.93 | 90.90 |
| 7 | Option Momentum | 12 | 33.3% | -31.11 | -0.16 | 0.87 | 126.09 |
| 8 | Gamma Scalp | 58 | 31.0% | -122.86 | -1.15 | 0.65 | 142.67 |
| 9 | ORB Strategy | 57 | 29.8% | -266.91 | -0.66 | 0.77 | 385.20 |

### TCS (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | Option Momentum | 9 | 55.6% | +498.74 | 0.92 | 2.67 | 172.28 |
| 2 | Momentum Breakout | 10 | 50.0% | +369.41 | 0.70 | 1.97 | 176.65 |
| 3 | Volume Spike | 14 | 42.9% | +258.24 | 0.48 | 1.47 | 199.53 |
| 4 | Mean Reversion | 26 | 38.5% | +225.98 | 0.30 | 1.19 | 343.74 |
| 5 | VWAP Reversion | 13 | 38.5% | -41.95 | -0.10 | 0.92 | 252.76 |
| 6 | Option Fade | 21 | 38.1% | -76.33 | -0.17 | 0.90 | 227.79 |
| 7 | ORB Strategy | 68 | 30.9% | -795.92 | -0.69 | 0.78 | 1147.90 |
| 8 | Straddle Breakout | 20 | 20.0% | -482.78 | -1.16 | 0.45 | 482.78 |
| 9 | Gamma Scalp | 49 | 28.6% | -341.27 | -1.36 | 0.56 | 409.97 |

### HDFCBANK (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | Mean Reversion | 21 | 52.4% | +103.15 | 0.65 | 1.54 | 58.53 |
| 2 | Option Fade | 23 | 47.8% | +69.41 | 0.57 | 1.41 | 68.37 |
| 3 | Volume Spike | 11 | 36.4% | +24.49 | 0.22 | 1.22 | 57.74 |
| 4 | ORB Strategy | 56 | 37.5% | +38.59 | 0.15 | 1.06 | 208.95 |
| 5 | Straddle Breakout | 16 | 31.2% | -36.19 | -0.35 | 0.77 | 110.97 |
| 6 | Gamma Scalp | 58 | 34.5% | -50.39 | -0.74 | 0.76 | 96.71 |
| 7 | VWAP Reversion | 13 | 23.1% | -60.61 | -0.76 | 0.53 | 104.51 |
| 8 | Option Momentum | 6 | 16.7% | -57.85 | -0.84 | 0.34 | 72.00 |
| 9 | Momentum Breakout | 11 | 18.2% | -125.66 | -1.41 | 0.22 | 125.91 |

### INFY (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | Straddle Breakout | 17 | 35.3% | -43.80 | -0.24 | 0.85 | 239.25 |
| 2 | Mean Reversion | 21 | 28.6% | -102.09 | -0.35 | 0.79 | 227.18 |
| 3 | Volume Spike | 21 | 28.6% | -105.75 | -0.37 | 0.78 | 196.81 |
| 4 | ORB Strategy | 86 | 31.4% | -279.62 | -0.46 | 0.86 | 829.26 |
| 5 | VWAP Reversion | 11 | 27.3% | -70.47 | -0.47 | 0.66 | 110.29 |
| 6 | Momentum Breakout | 17 | 23.5% | -178.41 | -0.70 | 0.60 | 237.94 |
| 7 | Gamma Scalp | 50 | 36.0% | -85.40 | -0.72 | 0.75 | 152.12 |
| 8 | Option Fade | 15 | 26.7% | -136.91 | -0.81 | 0.54 | 167.65 |
| 9 | Option Momentum | 16 | 12.5% | -364.39 | -1.61 | 0.26 | 423.91 |

### ICICIBANK (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | Mean Reversion | 26 | 50.0% | +291.52 | 1.00 | 1.81 | 60.73 |
| 2 | Straddle Breakout | 14 | 42.9% | +35.12 | 0.23 | 1.20 | 69.89 |
| 3 | VWAP Reversion | 13 | 38.5% | +14.49 | 0.11 | 1.09 | 80.12 |
| 4 | Option Fade | 20 | 40.0% | -2.67 | -0.02 | 0.99 | 78.24 |
| 5 | ORB Strategy | 64 | 31.2% | -221.15 | -0.56 | 0.81 | 315.00 |
| 6 | Option Momentum | 15 | 26.7% | -114.78 | -0.63 | 0.62 | 228.04 |
| 7 | Momentum Breakout | 20 | 20.0% | -222.93 | -1.07 | 0.48 | 288.89 |
| 8 | Volume Spike | 13 | 15.4% | -204.25 | -1.34 | 0.30 | 257.90 |
| 9 | Gamma Scalp | 50 | 26.0% | -153.40 | -1.73 | 0.49 | 186.82 |

### SBIN (NSE, daily)

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | VWAP Reversion | 22 | 50.0% | +113.51 | 0.92 | 1.80 | 77.32 |
| 2 | ORB Strategy | 74 | 41.9% | +230.02 | 0.76 | 1.30 | 157.00 |
| 3 | Straddle Breakout | 12 | 50.0% | +38.58 | 0.44 | 1.47 | 38.12 |
| 4 | Volume Spike | 18 | 38.9% | +56.75 | 0.38 | 1.32 | 145.22 |
| 5 | Mean Reversion | 23 | 43.5% | +38.57 | 0.24 | 1.16 | 104.59 |
| 6 | Momentum Breakout | 12 | 25.0% | -47.80 | -0.42 | 0.69 | 122.78 |
| 7 | Option Fade | 21 | 33.3% | -76.87 | -0.73 | 0.63 | 131.64 |
| 8 | Option Momentum | 10 | 20.0% | -76.45 | -0.82 | 0.45 | 89.53 |
| 9 | Gamma Scalp | 56 | 21.4% | -146.68 | -2.40 | 0.38 | 154.22 |

### NIFTY 50 (INDEX, daily) — Option strategies on index price

| Rank | Strategy | Trades | Win Rate | Net PnL | Sharpe | Profit Factor | Max DD |
|------|----------|--------|----------|---------|--------|---------------|--------|
| 1 | Option Fade | 15 | 66.7% | +3225.10 | 1.20 | 2.61 | 418.62 |
| 2 | Mean Reversion | 24 | 41.7% | +719.82 | 0.16 | 1.10 | 2607.60 |
| 3 | Straddle Breakout | 20 | 45.0% | +331.73 | 0.11 | 1.08 | 2167.69 |
| 4 | VWAP Reversion | 0 | 0.0% | 0.00 | 0.00 | 0.00 | 0.00 |
| 5 | Momentum Breakout | 20 | 30.0% | -370.02 | -0.09 | 0.94 | 1766.28 |
| 6 | Gamma Scalp | 59 | 40.7% | -545.08 | -0.29 | 0.90 | 1623.05 |
| 7 | ORB Strategy | 37 | 32.4% | -1454.88 | -0.26 | 0.88 | 3557.97 |
| 8 | Option Momentum | 23 | 30.4% | -2316.19 | -0.58 | 0.69 | 3127.73 |

*(Note: volume_spike errored on NIFTY 50 index data due to zero-volume division; all other 8 strategies ran successfully)*

### Cross-Stock Summary — Best Strategy Per Symbol

| Symbol | Best Strategy | Net PnL | Sharpe |
|--------|---------------|---------|--------|
| RELIANCE | VWAP Reversion | +476.83 | 2.02 |
| TCS | Option Momentum | +498.74 | 0.92 |
| HDFCBANK | Mean Reversion | +103.15 | 0.65 |
| INFY | Straddle Breakout | -43.80 | -0.24 |
| ICICIBANK | Mean Reversion | +291.52 | 1.00 |
| SBIN | VWAP Reversion | +113.51 | 0.92 |
| NIFTY 50 | Option Fade | +3225.10 | 1.20 |

**Consistent winners across symbols:** VWAP Reversion and Mean Reversion show positive PnL on the most symbols. Option Fade is the standout on NIFTY 50 index. INFY was the hardest symbol — no strategy achieved positive PnL.

### Portfolio Optimization Results

Max Sharpe allocation across strategies (9 strategies × 10 symbols):
- **mean_reversion 40% + vwap_reversion 33% + option_fade 27%**
- Portfolio Sharpe: **0.72** | Diversification score: **0.923**
- 35 uncorrelated strategy pairs identified

---

## ML Model Results

All models trained on 10-symbol pooled daily data (4,950 bars, 44 features, binary_10d label).

### Walk-Forward OOS Comparison (pooled, 10 symbols)

| Model | F1 Score | Notes |
|-------|----------|-------|
| **XGBoost (pooled)** | **0.7309** | Best overall — more data wins |
| LightGBM (pooled) | 0.470 | |
| LogReg (pooled, selected features) | **0.7438** | Best single-symbol (binary_10d + top-20 features) |
| CatBoost | 0.460 | |
| RandomForest | 0.465 | |

### Key Findings
- **Pooled training beats per-symbol**: XGBoost pooled F1=0.7309 vs mean per-symbol F1=0.5257 — more data dominates
- **Label matters**: `binary_10d` (10-day forward return) outperforms `binary_5d` significantly
- **Feature selection helps**: Removing correlated features (>0.95 threshold) drops 13 of 44 features and improves generalization
- **Top-20 feature selection** consistently matches or beats all-features baseline

### Commands
```bash
.venv/bin/python scripts/train_models.py --symbol RELIANCE --interval day --model all
.venv/bin/python scripts/improve_models.py        # Feature selection + Optuna tuning
.venv/bin/python scripts/train_multi_symbol.py    # Pooled 10-symbol training
```

---

## Paper Trading

Batch simulation: 54 runs (6 symbols × 9 strategies), last 100 daily bars each.
- Best: RELIANCE/mean_reversion (Sharpe 22.3), ICICIBANK/vwap_reversion (Sharpe 19.4)
- Walk-forward stability: `orb_strategy` won 3/4 folds (most consistent across periods)

```bash
.venv/bin/python scripts/paper_trading_batch.py   # 54 parallel simulations
.venv/bin/python scripts/walk_forward_paper.py    # Stability leaderboard
.venv/bin/python scripts/generate_daily_report.py # Daily HTML report
.venv/bin/python scripts/system_status.py         # Full system health dashboard
```

---

## OpenAlgo Integration (Recommended)

[OpenAlgo](https://github.com/marketcalls/openalgo) is a free, self-hosted broker API gateway supporting 30+ Indian brokers including Zerodha.

**Why use it:**
- Built-in **paper trading** with ₹1 Crore virtual capital (API Analyzer Mode)
- Same API endpoints for paper → live — zero code changes to switch
- Unified API across 30+ brokers (not locked to Zerodha)
- Self-hosted, data stays local

**Architecture with OpenAlgo:**
```
Strategy Code → ExecutionRouter → OpenAlgoBroker → OpenAlgo (localhost:5000) → Zerodha Kite
```

**Setup:**
```bash
# 1. Install OpenAlgo (Python 3.11+)
git clone https://github.com/marketcalls/openalgo
cd openalgo && pip install -r requirements.txt

# 2. Configure with your Zerodha credentials, start server
python app.py  # runs on http://localhost:5000

# 3. Use our OpenAlgo broker wrapper
# Add to .env:
OPENALGO_API_KEY=your_openalgo_key
OPENALGO_BASE_URL=http://localhost:5000
OPENALGO_PAPER_MODE=true   # set false for live
```

**Integration status:** `src/broker/openalgo_broker.py` — implements `Broker` interface, switches paper/live via config.

---

## Artifacts

| Artifact | Path |
|----------|------|
| Tournament HTML report | `artifacts/reports/tournament_RELIANCE_day.html` |
| Strategy correlation heatmap | `artifacts/reports/strategy_correlation.png` |
| Portfolio optimization report | `artifacts/reports/portfolio_backtest.html` |
| Paper trading batch results | `artifacts/paper/batch_2026-03-22.json` |
| Walk-forward paper results | `artifacts/paper/walk_forward_2026-03-22.json` |
| Daily HTML report | `artifacts/reports/daily_2026-03-22.html` |
| Trained models | `artifacts/models/*/` (versioned with metadata.json) |
