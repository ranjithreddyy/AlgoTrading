"""Tree-based gradient boosting models for trading signal classification."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

from src.models.baselines import BaseModel


class CatBoostModel(BaseModel):
    """CatBoost classifier with sensible trading defaults."""

    def __init__(self, **kwargs):
        defaults = dict(
            iterations=500,
            depth=6,
            learning_rate=0.05,
            verbose=0,
            random_seed=42,
            allow_writing_files=False,
        )
        defaults.update(kwargs)
        self._params = defaults
        self._model = CatBoostClassifier(**defaults)
        self._feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "CatBoostModel":
        X_clean, y_clean = self._clean(X, y)
        self._feature_names = list(X_clean.columns)
        self._model.fit(X_clean, y_clean)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        return self._model.predict(X_clean).flatten()

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        X_clean = self._clean(X)
        return self._model.predict_proba(X_clean)

    def get_params(self) -> Dict[str, Any]:
        return self._params.copy()

    def feature_importance(self) -> Optional[pd.Series]:
        try:
            imp = self._model.get_feature_importance()
            return pd.Series(imp, index=self._feature_names, name="importance").sort_values(ascending=False)
        except Exception:
            return None


class LightGBMModel(BaseModel):
    """LightGBM classifier with sensible trading defaults."""

    def __init__(self, **kwargs):
        defaults = dict(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            verbose=-1,
            random_state=42,
            n_jobs=-1,
        )
        defaults.update(kwargs)
        self._params = defaults
        self._model = LGBMClassifier(**defaults)
        self._feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LightGBMModel":
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


class XGBoostModel(BaseModel):
    """XGBoost classifier with sensible trading defaults."""

    def __init__(self, **kwargs):
        defaults = dict(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            verbosity=0,
            random_state=42,
            n_jobs=-1,
            use_label_encoder=False,
            eval_metric="logloss",
        )
        defaults.update(kwargs)
        self._params = defaults
        self._model = XGBClassifier(**defaults)
        self._feature_names: List[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "XGBoostModel":
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
