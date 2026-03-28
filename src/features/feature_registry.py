"""Feature registry for managing and computing features."""

from typing import Callable, Dict, List, Optional

import pandas as pd

from src.features import price_features, volatility_features, volume_features
from src.features import mean_reversion_features, regime_features


class FeatureRegistry:
    """Registry for feature computation functions.

    Each registered feature is a callable that accepts a DataFrame and returns
    a Series or DataFrame of computed values.
    """

    def __init__(self):
        self._registry: Dict[str, Callable[[pd.DataFrame], pd.Series | pd.DataFrame]] = {}

    def register(self, name: str, compute_fn: Callable) -> None:
        """Register a feature computation function.

        Args:
            name: Unique name for the feature group.
            compute_fn: Function that takes an OHLCV DataFrame and returns
                        a Series or DataFrame.
        """
        self._registry[name] = compute_fn

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all registered features.

        Args:
            df: OHLCV DataFrame.

        Returns:
            DataFrame with all computed features as columns.
        """
        results = {}
        for name, fn in self._registry.items():
            result = fn(df)
            if isinstance(result, pd.DataFrame):
                for col in result.columns:
                    results[col] = result[col]
            else:
                results[name] = result
        return pd.DataFrame(results, index=df.index)

    def compute_selected(self, df: pd.DataFrame, feature_names: List[str]) -> pd.DataFrame:
        """Compute only selected features.

        Args:
            df: OHLCV DataFrame.
            feature_names: List of registered feature names to compute.

        Returns:
            DataFrame with selected features as columns.
        """
        results = {}
        for name in feature_names:
            if name not in self._registry:
                raise KeyError(f"Feature '{name}' not registered. Available: {self.list_features()}")
            fn = self._registry[name]
            result = fn(df)
            if isinstance(result, pd.DataFrame):
                for col in result.columns:
                    results[col] = result[col]
            else:
                results[name] = result
        return pd.DataFrame(results, index=df.index)

    def list_features(self) -> List[str]:
        """List all registered feature names.

        Returns:
            Sorted list of feature names.
        """
        return sorted(self._registry.keys())


def create_default_registry() -> FeatureRegistry:
    """Create a registry with all standard features pre-registered.

    Returns:
        FeatureRegistry with all features registered.
    """
    registry = FeatureRegistry()

    # Price features
    registry.register("returns", price_features.returns)
    registry.register("ema", price_features.ema)
    registry.register("sma", price_features.sma)
    registry.register("ema_sma_gap", price_features.ema_sma_gap)
    registry.register("adx", price_features.adx)
    registry.register("vwap", price_features.vwap)
    registry.register("donchian", price_features.donchian)
    registry.register("trend_slope", price_features.trend_slope)

    # Volatility features
    registry.register("atr", volatility_features.atr)
    registry.register("realized_vol", volatility_features.realized_vol)
    registry.register("parkinson_vol", volatility_features.parkinson_vol)
    registry.register("garman_klass_vol", volatility_features.garman_klass_vol)
    registry.register("bollinger_bands", volatility_features.bollinger_bands)
    registry.register("bar_range_score", volatility_features.bar_range_score)
    registry.register("intraday_vol_percentile", volatility_features.intraday_vol_percentile)

    # Volume features
    registry.register("relative_volume", volume_features.relative_volume)
    registry.register("volume_spike", volume_features.volume_spike)
    registry.register("obv", volume_features.obv)
    registry.register("cmf", volume_features.cmf)
    registry.register("turnover", volume_features.turnover)
    registry.register("volume_momentum", volume_features.volume_momentum)

    # Mean reversion features
    registry.register("rsi", mean_reversion_features.rsi)
    registry.register("connors_rsi", mean_reversion_features.connors_rsi)
    registry.register("bollinger_zscore", mean_reversion_features.bollinger_zscore)
    registry.register("vwap_deviation", mean_reversion_features.vwap_deviation)
    registry.register("reversal_score", mean_reversion_features.reversal_score)

    # Regime features
    registry.register("hurst_exponent", regime_features.hurst_exponent)
    registry.register("vol_regime", regime_features.vol_regime)
    registry.register("trend_strength", regime_features.trend_strength)
    registry.register("mean_reversion_halflife", regime_features.mean_reversion_halflife)

    return registry


# Default registry instance
default_registry = create_default_registry()
