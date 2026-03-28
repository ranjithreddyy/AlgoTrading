"""Baseline ML models for trading signal classification."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler


class BaseModel(ABC):
    """Abstract base class for all ML models."""

    @abstractmethod
    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaseModel":
        """Fit the model on training data."""
        ...

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Return class predictions."""
        ...

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return class probabilities."""
        ...

    @abstractmethod
    def get_params(self) -> Dict[str, Any]:
        """Return model parameters."""
        ...

    @abstractmethod
    def feature_importance(self) -> Optional[pd.Series]:
        """Return feature importance as a Series indexed by feature name."""
        ...

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _clean(X: pd.DataFrame, y: Optional[pd.Series] = None):
        """Drop rows with NaN in X (and corresponding y rows)."""
        mask = X.notna().all(axis=1)
        X_clean = X.loc[mask].copy()
        if y is not None:
            y_clean = y.loc[mask].copy()
            return X_clean, y_clean
        return X_clean


class LogisticRegressionModel(BaseModel):
    """Logistic Regression with StandardScaler pre-processing."""

    def __init__(self, **kwargs):
        defaults = dict(max_iter=1000, solver="lbfgs", C=1.0, random_state=42)
        defaults.update(kwargs)
        self._params = defaults
        self._scaler = StandardScaler()
        self._model = LogisticRegression(**defaults)
        self._feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogisticRegressionModel":
        X_clean, y_clean = self._clean(X, y)
        self._feature_names = list(X_clean.columns)
        X_scaled = self._scaler.fit_transform(X_clean)
        self._model.fit(X_scaled, y_clean)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        X_scaled = self._scaler.transform(X_clean)
        return self._model.predict(X_scaled)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        X_scaled = self._scaler.transform(X_clean)
        return self._model.predict_proba(X_scaled)

    def get_params(self) -> Dict[str, Any]:
        return self._params.copy()

    def feature_importance(self) -> Optional[pd.Series]:
        if hasattr(self._model, "coef_"):
            coef = np.abs(self._model.coef_).mean(axis=0)
            return pd.Series(coef, index=self._feature_names, name="importance").sort_values(ascending=False)
        return None


class RandomForestModel(BaseModel):
    """Random Forest classifier."""

    def __init__(self, **kwargs):
        defaults = dict(n_estimators=200, max_depth=8, random_state=42, n_jobs=-1)
        defaults.update(kwargs)
        self._params = defaults
        self._model = RandomForestClassifier(**defaults)
        self._feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "RandomForestModel":
        X_clean, y_clean = self._clean(X, y)
        self._feature_names = list(X_clean.columns)
        self._model.fit(X_clean, y_clean)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        return self._model.predict(X_clean)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        return self._model.predict_proba(X_clean)

    def get_params(self) -> Dict[str, Any]:
        return self._params.copy()

    def feature_importance(self) -> Optional[pd.Series]:
        if hasattr(self._model, "feature_importances_"):
            return pd.Series(
                self._model.feature_importances_,
                index=self._feature_names,
                name="importance",
            ).sort_values(ascending=False)
        return None
