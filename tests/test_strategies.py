"""Tests for strategy framework: base, concrete strategies, registry, backtest engine."""

import pytest

from src.strategies.base import Strategy, StrategyConfig, BacktestResult
from src.strategies.momentum_breakout import MomentumBreakoutStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.registry import StrategyRegistry
from src.backtests.engine import BacktestEngine
from src.backtests.batch_runner import BatchRunner


# ── StrategyConfig ───────────────────────────────────────────────────────────

def test_strategy_config():
    """StrategyConfig creation with all fields."""
    cfg = StrategyConfig(
        name="test_strategy",
        family="momentum",
        asset_class="stock",
        params={"fast_period": 9, "slow_period": 21},
        param_grid={"fast_period": [5, 9], "slow_period": [15, 21]},
    )
    assert cfg.name == "test_strategy"
    assert cfg.family == "momentum"
    assert cfg.asset_class == "stock"
    assert cfg.params["fast_period"] == 9
    assert len(cfg.param_grid["fast_period"]) == 2


# ── Momentum Breakout ────────────────────────────────────────────────────────

def test_momentum_breakout_instantiate():
    """Create MomentumBreakoutStrategy and verify default params."""
    cfg = StrategyConfig(name="momentum_breakout", family="momentum", asset_class="stock")
    strategy = MomentumBreakoutStrategy(cfg)
    assert strategy.p["fast_period"] == 9
    assert strategy.p["slow_period"] == 21
    assert strategy.p["volume_multiplier"] == 1.2
    assert isinstance(strategy, Strategy)


# ── Mean Reversion ───────────────────────────────────────────────────────────

def test_mean_reversion_instantiate():
    """Create MeanReversionStrategy and verify default params."""
    cfg = StrategyConfig(name="mean_reversion", family="mean_reversion", asset_class="stock")
    strategy = MeanReversionStrategy(cfg)
    assert strategy.p["rsi_period"] == 14
    assert strategy.p["oversold"] == 30
    assert strategy.p["overbought"] == 70
    assert isinstance(strategy, Strategy)


# ── All strategies have param_grid ───────────────────────────────────────────

def test_all_strategies_have_param_grid():
    """Every concrete strategy returns a non-empty param grid."""
    strategies = [MomentumBreakoutStrategy, MeanReversionStrategy]
    for cls in strategies:
        cfg = StrategyConfig(
            name=getattr(cls, "__strategy_name__", cls.__name__),
            family=getattr(cls, "__default_family__", "unknown"),
            asset_class="stock",
        )
        instance = cls(cfg)
        grid = instance.get_param_grid()
        assert isinstance(grid, dict)
        assert len(grid) > 0, f"{cls.__name__} returned empty param_grid"


# ── Registry ─────────────────────────────────────────────────────────────────

def test_registry_discover():
    """auto_discover finds concrete strategy classes."""
    registry = StrategyRegistry()
    registry.auto_discover()
    names = registry.list_all()
    assert len(names) >= 2  # at least momentum_breakout and mean_reversion
    assert "momentum_breakout" in names
    assert "mean_reversion" in names


# ── BacktestEngine ───────────────────────────────────────────────────────────

def test_backtest_engine_runs(sample_bars):
    """BacktestEngine produces a BacktestResult with correct types."""
    cfg = StrategyConfig(
        name="momentum_breakout",
        family="momentum",
        asset_class="stock",
        params={"fast_period": 5, "slow_period": 10},
    )
    strategy = MomentumBreakoutStrategy(cfg)
    engine = BacktestEngine()
    result = engine.run(strategy, sample_bars)

    assert isinstance(result, BacktestResult)
    assert result.strategy_name == "momentum_breakout"
    assert isinstance(result.total_trades, int)
    assert isinstance(result.net_pnl, float)
    assert isinstance(result.equity_curve, list)
    assert len(result.equity_curve) > 0


# ── BatchRunner ──────────────────────────────────────────────────────────────

def test_batch_runner(sample_bars):
    """BatchRunner runs multiple strategies and returns results."""
    configs = []
    for name, cls in [("momentum_breakout", MomentumBreakoutStrategy),
                      ("mean_reversion", MeanReversionStrategy)]:
        cfg = StrategyConfig(name=name, family="test", asset_class="stock")
        configs.append((cls, cfg))

    runner = BatchRunner(n_workers=1)
    results = runner.run_all(configs, sample_bars)

    assert isinstance(results, list)
    assert len(results) == 2
    for r in results:
        assert isinstance(r, BacktestResult)


# ── Parameter Sweep ──────────────────────────────────────────────────────────

def test_parameter_sweep(sample_bars):
    """Parameter sweep produces multiple results (one per combination)."""
    runner = BatchRunner(n_workers=1)
    grid = {
        "fast_period": [5, 9],
        "slow_period": [15, 21],
    }
    results = runner.run_parameter_sweep(
        MomentumBreakoutStrategy,
        param_grid=grid,
        data_df=sample_bars,
    )

    assert isinstance(results, list)
    # 2 * 2 = 4 combinations
    assert len(results) == 4
    for r in results:
        assert isinstance(r, BacktestResult)
