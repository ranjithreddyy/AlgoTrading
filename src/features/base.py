"""Base feature classes for the feature computation library."""

from abc import ABC, abstractmethod
from typing import List

import pandas as pd


class Feature(ABC):
    """Abstract base class for a single feature."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this feature."""
        pass

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series:
        """Compute the feature from an OHLCV DataFrame.

        Args:
            df: DataFrame with columns date, open, high, low, close, volume.

        Returns:
            pd.Series with computed feature values, same index as df.
        """
        pass


class FeatureSet:
    """Holds multiple Feature instances and computes them all at once."""

    def __init__(self, features: List[Feature] | None = None):
        self.features: List[Feature] = features or []

    def add(self, feature: Feature) -> None:
        self.features.append(feature)

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all features and return as a DataFrame.

        Args:
            df: DataFrame with columns date, open, high, low, close, volume.

        Returns:
            pd.DataFrame with one column per feature.
        """
        results = {}
        for feature in self.features:
            result = feature.compute(df)
            if isinstance(result, pd.DataFrame):
                for col in result.columns:
                    results[col] = result[col]
            else:
                results[feature.name] = result
        return pd.DataFrame(results, index=df.index)
