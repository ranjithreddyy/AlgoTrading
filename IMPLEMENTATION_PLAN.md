# Trading Strategy Implementation Plan

## Summary

This repository will be expanded from a Zerodha API prototype into a research, backtesting, paper-trading, and live-trading platform for Indian intraday trading.

The target `v1` scope is:

- Intraday only
- `NSE` cash stocks
- `NIFTY` weekly options, long-premium only
- Paper trading first
- Live trading only after stable out-of-sample and paper-trading performance

The plan explicitly does **not** optimize for a fixed rupee profit target per day. The system should optimize for:

- Positive post-cost expectancy
- Controlled drawdown
- Stable performance across regimes
- Slippage-aware execution
- Safe autonomous operation
- Graceful degradation under failure conditions

Research capital assumptions for paper/backtest:

- Base notional: `INR 5,00,000`
- Stress notional: `INR 10,00,000`
- Stress daily loss bands: `INR 10,000`, `INR 20,000`, `INR 30,000`

Live capital and live loss limits will be finalized only after paper trading is stable.

## Current Repo Baseline

Current repository strengths:

- Zerodha Kite authentication exists
- Historical data fetch path exists
- Basic Backtrader backtest exists
- Basic live-trading scaffold exists

Current repository gaps that must be fixed before strategy work:

- `main.py` has missing/incorrect command wiring
- Hard-coded paths point to a different local machine path
- Current live trader is not option-chain aware
- Current backtest flow is too simple for Indian intraday execution modeling
- No instrument-master archive exists for expired options
- No order-state persistence, risk engine, or paper-trading ledger exists
- No feature store, model training pipeline, or walk-forward validation flow exists

## Operating Assumptions

- Timezone for all market logic: `Asia/Kolkata`
- Exchange focus: `NSE` for stocks and `NFO` for options
- Instruments for `v1`:
  - `15-30` highly liquid cash stocks
  - `NIFTY` weekly options only
- `SENSEX` options remain paper-only until liquidity and slippage logs justify enabling them
- No futures in `v1`
- No overnight positions
- No option selling in `v1`
- Kite API rate limits apply: `3 req/sec` for historical data, `10 orders/sec` for order placement
- Kite access tokens expire daily; token refresh must happen before market open
- No more than one live strategy family should be promoted at a time during initial rollout

## Trading Calendar and Market Sessions

The system must be calendar-aware:

- Maintain an NSE holiday calendar, refreshed annually
- Do not run strategies or place orders on exchange holidays
- Recognize special sessions: `Muhurat Trading`, early close days
- Handle monthly `F&O expiry Thursdays` as distinct regime (higher volatility, gamma risk)
- Handle weekly `NIFTY option expiry` days with special risk rules (rapid theta decay, wider spreads)
- Track `RBI policy days`, `Union Budget day`, and `quarterly earnings` dates as high-impact event days
- Pre-market session (`09:00-09:08`) data should be captured for opening price discovery signals
- Regular market: `09:15-15:30`, closing session: `15:30-15:40`

## Corporate Actions and Data Adjustments

Historical data must account for corporate actions to avoid phantom signals:

- Adjust for stock splits and bonuses in historical candle data
- Adjust for ex-dividend dates when computing returns
- Flag symbols undergoing corporate action and exclude them from universe on adjustment dates
- Kite historical API returns unadjusted data; the ingestion layer must apply adjustments before storage
- Maintain a corporate actions log per symbol for audit

## Circuit Breaker and Exchange Halt Handling

Indian markets have circuit breakers that the system must handle:

- Stock-level upper/lower circuit limits: exclude circuit-hit stocks from signal generation
- Index-level market-wide circuit breakers (`10%`, `15%`, `20%`): halt all strategy activity
- Detect circuit conditions via price hitting limit + zero bid/ask depth
- Never place orders on circuit-locked stocks
- If a held position's stock hits a circuit, mark it for manual review instead of automated exit

## Target Architecture

Create the following structure inside the repo:

```text
src/
  config/
    settings.py
    trading_config.py
  core/
    clock.py
    calendar.py
    enums.py
    types.py
    utils.py
    logger.py
  broker/
    kite_client.py
    paper_broker.py
    execution_router.py
    order_reconciler.py
  instruments/
    instrument_master.py
    option_chain.py
    symbol_resolver.py
    corporate_actions.py
    greeks.py
  data/
    ingestion.py
    historical_loader.py
    websocket_feed.py
    storage.py
    quality.py
  features/
    base.py
    price_features.py
    volatility_features.py
    volume_features.py
    microstructure_features.py
    options_features.py
    regime_features.py
    cross_asset_features.py
    feature_registry.py
  labels/
    triple_barrier.py
    horizon_returns.py
    meta_labels.py
  models/
    baselines.py
    tree_models.py
    deep_models.py
    model_registry.py
    inference.py
  research/
    universe.py
    strategy_rules.py
    train.py
    walk_forward.py
    evaluate.py
    selection.py
  backtests/
    engine.py
    fills.py
    costs.py
    portfolio.py
    reports.py
  risk/
    sizing.py
    limits.py
    kill_switch.py
    compliance.py
  live/
    signal_service.py
    trade_loop.py
    session_manager.py
    monitoring.py
    crash_recovery.py
scripts/
  sync_instruments.py
  ingest_history.py
  train_models.py
  run_backtests.py
  run_paper_trading.py
  run_live_trading.py
tests/
```

### Concurrency Model

- Use `asyncio` as the primary concurrency model for the live trading loop
- WebSocket feed, signal generation, and order management run as async tasks
- CPU-bound work (feature computation, model inference) runs in a `ProcessPoolExecutor`
- Each strategy family runs as an independent async task with its own state
- Use `asyncio.Queue` for communication between feed, signal, and execution layers

### Component Wiring

- Use constructor-based dependency injection across all modules
- Core interfaces (`Broker`, `DataFeed`, `RiskEngine`) are abstract base classes
- `PaperBroker` and `KiteBroker` implement the same `Broker` interface
- A `SessionFactory` wires all components together at startup based on config
- This enables unit testing with mocked dependencies

## Storage Design

Use local-first storage with partitioned `Parquet` and `DuckDB`.

- Instrument master snapshots:
  - `data/raw/instruments/YYYY-MM-DD/instruments.parquet`
- Historical candles:
  - `data/market/exchange=<exchange>/symbol=<symbol>/interval=<interval>/date=<YYYY-MM-DD>.parquet`
- Option chain snapshots:
  - `data/options/underlying=<underlying>/expiry=<expiry>/date=<YYYY-MM-DD>.parquet`
- Features:
  - `data/features/model_universe=<name>/date=<YYYY-MM-DD>.parquet`
- Labels:
  - `data/labels/task=<task>/date=<YYYY-MM-DD>.parquet`
- Backtest artifacts:
  - `artifacts/backtests/<run_id>/`
- Trained models:
  - `artifacts/models/<model_name>/<version>/`
- Paper trading logs:
  - `artifacts/paper/<date>/`
- Live trading logs:
  - `artifacts/live/<date>/`

Non-negotiable rules:

- Archive the daily instrument master. Expired option tokens are not recoverable later unless they are cached when live.
- Use Snappy or Zstandard compression for Parquet files to manage storage growth.

### Data Retention Policy

- Raw instrument masters: retain indefinitely (small files, critical for survivorship bias)
- Minute-bar candles: retain indefinitely (core research asset)
- Feature files: retain last `6 months`; regenerate from raw data if older features are needed
- Backtest artifacts: retain last `20` runs per strategy; archive older runs to cold storage
- Paper/live trade logs: retain indefinitely (audit requirement)
- Model artifacts: retain all promoted versions; prune non-promoted versions older than `3 months`

### Trade and Order Log Storage

- Use SQLite (not Parquet) for trade logs, order logs, and signal logs
- Relational queries on trade logs (filter by strategy, date range, outcome) are common and SQLite handles them better than Parquet scans
- Keep one SQLite database per month to avoid unbounded file growth
- Schema must include: `trade_id`, `strategy_id`, `model_version`, `signal_time`, `entry_time`, `exit_time`, `entry_price`, `exit_price`, `quantity`, `side`, `pnl`, `slippage`, `reason`

## Data Ingestion Plan

### Phase 0: Repo Stabilization

1. Replace hard-coded absolute paths with repo-relative paths.
2. Convert current `src/kite_client.py` into a broker client layer with retries, timeout handling, and logging.
3. Add environment loading via `.env`.
4. Normalize command entrypoints in `main.py` or move to `scripts/`.
5. Preserve the existing code as a temporary compatibility layer only until the new modules exist.

### Phase 1: Instrument and History Pipeline

1. Add a daily job to download full instrument masters from Kite.
2. Build symbol-resolution utilities for:
   - NSE cash symbols
   - NIFTY option chain selection
   - nearest weekly expiry
   - ATM and nearby strikes
3. Add historical loaders for:
   - `1minute`
   - `3minute`
   - `5minute`
   - `15minute`
   - `day`
4. For F&O historical calls, request `oi=1` where available.
5. Add ingestion commands that backfill by date range and avoid duplicate writes.
6. Add data quality validation on every ingestion batch:
   - reject bars where `high < low` or `close` outside `[low, high]`
   - detect and flag gaps in minute-bar sequences (missing bars)
   - detect volume anomalies (zero volume during market hours)
   - apply corporate action adjustments before writing to storage
   - log quality metrics per ingestion run
7. Respect Kite API rate limits (`3 req/sec` for historical data) with adaptive throttling and backoff.

### Phase 2: Live Market Data

1. Add WebSocket streaming for:
   - stock universe
   - live NIFTY option chain subset
2. Persist intraday minute bars from live ticks.
3. Track stream health:
   - reconnect count
   - time since last tick
   - symbol subscription mismatches
4. Implement network resilience:
   - exponential backoff on WebSocket reconnect (max `30s`)
   - fall back to REST polling if WebSocket is down for more than `2 minutes`
   - alert if data staleness exceeds `60 seconds` during market hours
   - detect and handle Kite API maintenance windows gracefully

## Tradable Universe Rules

### Stocks

Daily stock universe should be selected before market open using:

- `NSE` only
- price above configurable minimum
- high recent average traded value
- small median bid-ask spread
- no auction-only or illiquid names
- avoid names with repeated large gap/slippage anomalies

Initial target: `15-30` names.

### Options

`v1` option universe:

- Underlying: `NIFTY`
- Expiry: nearest weekly expiry
- Strikes: `ATM`, `ATM +/- 1`, `ATM +/- 2`
- Long only: buy `CE` or `PE`
- One position per option trade
- No naked short options

Option entry filters:

- minimum traded volume
- acceptable spread
- acceptable premium for capital
- OI and volume confirmation
- avoid far OTM low-liquidity contracts

## Feature Library

Build one shared feature library first. Do not hardcode indicators inside strategy classes.

### Price and Trend Features

- returns over multiple horizons
- rolling trend slope
- `EMA` and `SMA` gaps
- `ADX`
- anchored `VWAP`
- opening range breakout distance
- Donchian breakout distance

### Mean Reversion Features

- `RSI`
- Connors RSI
- Bollinger z-score
- price vs VWAP deviation
- short-horizon reversal score

### Volatility Features

- `ATR`
- realized volatility
- Parkinson volatility
- Garman-Klass volatility
- intraday vol percentile
- bar range expansion score

### Volume and Flow Features

- relative volume
- volume spike score
- `OBV`
- `CMF`
- turnover percentile
- burstiness over last `N` minutes

### Microstructure Features

- spread in ticks and bps
- depth imbalance if available
- microprice skew if available
- quote freshness
- last-trade-to-mid distance

### Market Context Features

- `NIFTY` spot return
- sector index trend
- India VIX if integrated later
- market breadth proxy
- opening gap classification
- time-of-day bucket

### Cross-Asset and Correlation Features

- rolling correlation of stock vs NIFTY
- sector co-movement score
- beta to NIFTY
- dispersion score (how far individual stocks move vs the index)
- cross-sectional rank of returns, volume, and volatility

### Regime Detection Features

- Hidden Markov Model regime state (trend, range, volatile)
- rolling Hurst exponent
- volatility regime percentile (low/normal/high/extreme)
- trend strength persistence score
- mean-reversion half-life estimate

### Options Features

- moneyness
- time to expiry
- premium percentile
- option return over multiple horizons
- OI change
- volume/OI ratio
- ATM straddle move
- call-put relative strength

### Options Greeks (Calculated)

- delta (Black-Scholes or binomial)
- gamma
- theta
- vega
- implied volatility (via Newton-Raphson or bisection on BS model)

## Strategy Families

Implement multiple narrow strategy families instead of one giant strategy.

### Strategy Family A: Stock Momentum Breakout

Use when regime classifier says trend regime.

Entry conditions:

- opening range break or post-open consolidation break
- anchored VWAP confirmation
- above-average relative volume
- trend filter positive
- spread below threshold

Exit conditions:

- target
- stop loss
- time stop
- VWAP failure
- end-of-day forced exit

### Strategy Family B: Stock Intraday Mean Reversion

Use only in range regimes.

Entry conditions:

- strong deviation from VWAP or Bollinger band
- exhaustion signal from momentum oscillator
- no high-volatility regime flag
- adequate liquidity

Exit conditions:

- reversion to VWAP
- stop loss
- max holding time
- end-of-day forced exit

### Strategy Family C: NIFTY Option Momentum

Use when spot trend and option activity align.

Entry conditions:

- NIFTY spot breakout/trend confirmation
- nearest-weekly option premium expanding
- acceptable spread and volume
- OI or volume confirmation
- choose `CE` for bullish, `PE` for bearish

Exit conditions:

- fixed stop
- trailing stop
- time stop
- underlying trend failure
- end-of-day forced exit

### Strategy Family D: NIFTY Option Range Fade

Use only in non-trend sessions.

Entry conditions:

- spot mean-reversion setup
- option spread acceptable
- low trend score
- premium not already collapsed

Exit conditions:

- quick target
- tighter stop
- shorter holding window
- end-of-day forced exit

### Strategy Correlation and Diversification

- Measure rolling correlation of daily PnL across strategy families
- Do not deploy two highly correlated strategies simultaneously; they compound drawdown risk
- Use a portfolio-level Sharpe ratio, not individual strategy Sharpes, for capital allocation
- Track marginal contribution to risk for each active strategy

### Expiry Day Special Handling for Options

- On NIFTY weekly expiry days:
  - tighten stop losses by `50%`
  - reduce max position size for options by `50%`
  - no new option entries in last `60 minutes` before expiry
  - force-exit all option positions at least `15 minutes` before close
  - flag gamma risk when delta moves faster than expected

## Labeling and Prediction Targets

Use classification and meta-labeling first. Do not make direct price forecasting the primary `v1` objective.

Primary targets:

- `trade/no_trade`
- `long/short/no_trade` for stocks
- `buy_call/buy_put/no_trade` for options
- expected post-cost return bucket

Labeling methods:

- fixed-horizon forward returns
- triple-barrier labels
- meta-labels for execution filtering

Secondary targets:

- predicted drawdown bucket
- predicted holding-time bucket
- predicted slippage bucket

## Model Plan

### Production Baselines

These should be built first and treated as likely `v1` winners:

- logistic regression
- random forest
- `LightGBM`
- `XGBoost`
- `CatBoost`

### Deep Learning Challengers

These are challengers, not first deployment choices:

- `N-BEATSx`
- `N-HiTS`
- `Temporal Fusion Transformer`
- `PatchTST`
- `TSMixer`
- `TimeMixer`

### Foundation-Model Challengers

Evaluate only after the classical baselines are stable:

- `Chronos`
- `TimesFM`
- `MOMENT`
- `Time-MoE`
- `TimeFound`

### Ensemble Policy

Use a stacked approach:

1. Regime model
2. Signal model
3. Meta-label model
4. Optional uncertainty model for sizing and stop placement

Do not average every model blindly. Promote only the models that improve out-of-sample net performance and stability.

## Training Pipeline

1. Build datasets by session date and symbol.
2. Split using walk-forward windows.
3. Apply purging and embargo to avoid leakage.
4. Train baseline models first.
5. Evaluate on strict out-of-sample slices.
6. Save:
   - model artifact
   - feature list
   - training range
   - validation metrics
   - cost assumptions
7. Register every successful model version.

### Walk-Forward Retraining Schedule

- Retrain baseline models every `5 trading days` using expanding or rolling windows
- Retrain deep models every `20 trading days` (higher computational cost)
- Evaluate model staleness: if live prediction accuracy drops below `OOS baseline - 2 sigma`, trigger early retrain
- Track feature importance drift across retraining windows
- Alert if top-10 feature ranking changes significantly between consecutive retrains

### Feature Importance and Decay Tracking

- Log SHAP values or permutation importance at every training run
- Track which features contribute most to prediction vs which are noise
- Auto-flag features whose importance drops below a configurable threshold for `3` consecutive windows
- Remove or replace decayed features in subsequent training runs

Minimum model metadata:

- model name
- version
- git commit hash
- train dates
- validation dates
- features used
- label definition
- cost model version

## Backtesting Design

Backtrader may be retained only for quick smoke tests. The production research path should use a custom event-driven backtest engine.

The backtest engine must support:

- minute-by-minute event simulation
- long stock trades
- long option trades
- realistic commissions and statutory charges
- spread and slippage
- partial fills
- rejected orders
- missed fills
- stop and target handling
- intraday position limits
- end-of-day flattening

Survivorship bias controls:

- Use point-in-time universe snapshots from archived instrument masters
- Do not backtest with today's NIFTY 50 constituents on 2-year-old data
- Reconstruct daily universe using the instrument master from that date
- Symbols that were delisted, suspended, or moved out of the index must appear in historical backtests

Backtest fill logic:

- use next-bar execution at minimum
- apply spread-based entry/exit penalty
- use liquidity-aware slippage model
- block fills on bars with insufficient volume

## Cost Model

Include all costs relevant to Indian trading:

- brokerage assumptions
- exchange transaction charges
- STT
- GST
- SEBI charges
- stamp duty
- spread
- modeled slippage

Keep a versioned cost model so results remain reproducible.

## Risk Engine

Risk controls must exist before any live deployment.

### Session-Level Limits

- daily max loss
- daily max trades
- max consecutive losses
- max notional exposure
- max simultaneous positions
- trading disabled after kill-switch trigger

### Position-Level Limits

- max capital allocation per trade
- max premium allocation per option trade
- stop loss required on every trade
- max holding time
- no averaging down

### Time Rules

- no trading in first few minutes after open unless strategy explicitly allows it
- no new positions near market close
- forced intraday exit before close

### Crash Recovery and State Persistence

- Persist all open positions and pending orders to a local state file (JSON or SQLite) on every state change
- On startup during market hours, reconcile local state against broker positions via `kite.positions()`
- If positions exist on broker but not in local state, flag for manual review; do not auto-trade against unknown positions
- If the system was down and missed exit signals, attempt graceful exit on reconnection (within risk limits)
- Log every crash/restart event with timestamp and recovery actions taken

### Token and Authentication Resilience

- Refresh Kite access token automatically before market open each day
- If token expires mid-session (should not happen with daily tokens, but as a safety net): pause all new order activity, alert immediately, attempt re-authentication
- Never cache tokens beyond their expiry window

## Paper Trading Plan

Paper trading must use the same signal and execution path as live trading, except broker routing is replaced with a simulated broker.

Paper mode requirements:

- generate candidate signals in real time
- simulate fills with spread/slippage
- keep full trade ledger
- track PnL by strategy family
- track model confidence vs realized outcome
- generate daily report

Minimum paper promotion criteria before live:

- at least `20` trading sessions
- at least `200` paper trades
- positive post-cost PnL
- profit factor greater than `1.2`
- no repeated risk-limit breaches
- stable performance across different market regimes

## Live Trading Rollout

### Stage 1: Shadow Mode

- generate signals
- no orders
- compare predicted trades with actual market outcomes

### Stage 2: Paper Broker

- full real-time simulation
- same code path as live
- validate reconciliation and risk controls

### Stage 3: Micro Live

- one strategy family only
- one small universe only
- strict capital cap
- manual monitoring required

### Stage 4: Controlled Scale-Up

- increase symbol count gradually
- add second strategy family only after first is stable
- scale capital only after live slippage matches assumptions

## Monitoring and Reporting

Create daily and intraday reports for:

- gross and net PnL
- slippage by strategy
- hit rate
- expectancy per trade
- drawdown
- kill-switch events
- model confidence calibration
- paper vs backtest drift
- live vs paper drift

### Execution Quality Analytics

- compare fill price vs VWAP over holding period (implementation shortfall)
- compare fill price vs mid-price at signal time
- track order-to-fill latency
- measure realized spread cost vs assumed spread cost
- flag trades where realized slippage exceeds `2x` the modeled slippage

### Logging Framework

- Use Python `logging` with `structlog` for structured JSON log output
- Log levels: `DEBUG` for tick-level data, `INFO` for trade events, `WARNING` for risk threshold approaches, `ERROR` for failures, `CRITICAL` for kill-switch triggers
- Every log entry must include: `timestamp`, `session_date`, `component`, `strategy_id` (if applicable)
- Rotate log files daily; retain for `90 days`
- In live mode, stream `WARNING+` logs to a monitoring channel (Telegram bot or similar)

Add alerts for:

- token/auth failure
- websocket disconnect
- stale data
- repeated order rejections
- abnormal slippage
- breach of risk limits

## Compliance and Safety

Design with auditability from the start.

- keep full order and signal logs
- persist strategy ID and model version on every trade decision
- keep pre-trade reason fields
- keep post-trade outcome fields
- keep manual kill-switch support
- keep a config switch to disable autonomous order placement instantly

Live rollout should assume current `SEBI` retail algo requirements apply during implementation planning.

## Implementation Order

### Milestone 1: Foundation

- stabilize repo entrypoints and config
- set up structured logging framework
- add NSE trading calendar and holiday awareness
- add instrument master archive
- add corporate actions tracking and price adjustment
- add historical ingestion with data quality validation
- add parquet and duckdb storage with compression
- add SQLite trade log schema
- add tests for symbol resolution and ingestion

### Milestone 2: Research Pipeline

- build feature library
- build labels
- build walk-forward training and evaluation
- implement stock-only baseline strategies
- produce first real backtest reports

### Milestone 3: Option Research

- add option-chain resolver
- add options Greeks calculation (delta, gamma, theta, vega, IV)
- add option features and labels
- add expiry-day special risk rules
- add option-aware backtests with survivorship-bias-free universe
- evaluate NIFTY option momentum and fade families
- measure strategy correlation across families

### Milestone 4: Paper Trading

- add websocket feed with network resilience
- add paper broker
- add risk engine with circuit breaker detection
- add crash recovery and state persistence
- add real-time reporting with execution quality analytics
- run paper trading for required sessions

### Milestone 5: Live Readiness

- add execution router and reconciler
- add kill switch and monitoring
- add token refresh automation
- add Telegram/webhook alert integration
- enable shadow mode
- enable micro-live only after paper criteria are met

## Acceptance Criteria

The platform is ready for paper trading when all of the following are true:

- instrument masters are archived daily
- historical data ingestion is reproducible
- features and labels are versioned
- at least one stock strategy and one NIFTY option strategy pass out-of-sample tests
- backtests include costs and slippage
- paper broker reproduces the live execution path
- risk controls are enforced automatically

The platform is ready for micro-live when all of the following are true:

- paper criteria are met
- shadow mode is stable
- reconciliation works
- no critical data or execution outages remain
- slippage assumptions are validated in paper logs
- manual shutdown and automated kill-switch both work

## Testing Plan

Add automated tests for:

- symbol and option contract resolution
- instrument archive loading
- historical ingestion deduplication
- feature generation correctness
- label generation correctness
- walk-forward split correctness
- cost model correctness
- risk-limit enforcement
- simulated broker fills
- order reconciliation

Add integration tests for:

- end-to-end backtest run
- end-to-end paper-trading session replay
- live signal loop with mocked broker responses

Add stress/edge-case tests for:

- circuit breaker detection and halt behavior
- crash recovery and state reconciliation
- token expiry mid-session handling
- WebSocket disconnect and reconnect behavior
- expiry-day risk rule enforcement
- corporate action adjustment correctness
- concurrent strategy execution under load

## Suggested Dependency Additions

Likely additions to `requirements.txt`:

- `python-dotenv`
- `scikit-learn`
- `lightgbm`
- `xgboost`
- `catboost`
- `optuna`
- `duckdb`
- `pyarrow`
- `polars`
- `pydantic`
- `sqlalchemy`
- `tenacity`
- `pytest`
- `pytest-asyncio`
- `torch`
- `structlog`
- `shap`
- `scipy`
- `hmmlearn`
- `py-vollib` (for options Greeks and implied volatility)
- `exchange-calendars` or `trading-calendars` (for NSE holiday awareness)

Deep and foundation-model dependencies should be added only when their evaluation phase begins.

## References

- Zerodha historical data: `https://kite.trade/docs/connect/v3/historical/`
- Zerodha orders: `https://kite.trade/docs/connect/v3/orders/`
- Zerodha WebSocket: `https://kite.trade/docs/connect/v3/websocket/`
- Zerodha postbacks: `https://kite.trade/docs/connect/v3/postbacks/`
- SEBI retail algo circular, February 4, 2025
- SEBI extension circular, September 30, 2025
- `N-BEATS`, `PatchTST`, `TFT`, `TSMixer`, `TimeMixer`, `Chronos`, `TimesFM`, `MOMENT`, `Time-MoE`, and `TimeFound` as challenger model references

## Immediate Next Step

Implementation should begin with `Milestone 1` only.

Do not start by coding models first.

The correct first sequence is:

1. stabilize config and command entrypoints
2. archive instruments
3. ingest historical data
4. create storage layout
5. build symbol resolution and option-chain selection
6. then start feature and model work
