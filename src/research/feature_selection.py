"""Feature selection utilities for ML trading models."""

from typing import Optional

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.metrics import f1_score
from sklearn.model_selection import TimeSeriesSplit

from src.models.baselines import BaseModel


def compute_feature_importance(
    model: BaseModel,
    X: pd.DataFrame,
    y: pd.Series,
    method: str = "permutation",
) -> pd.Series:
    """Compute feature importance for a fitted model.

    Args:
        model: A fitted BaseModel instance.
        X: Feature DataFrame (used as background for permutation).
        y: Label Series.
        method: 'permutation' or 'model' (uses built-in importance if available).

    Returns:
        pd.Series of importances sorted descending, indexed by feature name.
    """
    if method == "model":
        imp = model.feature_importance()
        if imp is not None:
            return imp.sort_values(ascending=False)
        # Fall back to permutation if model doesn't support built-in importance
        method = "permutation"

    if method == "permutation":
        # Fit the model if not already fitted (try predict to check)
        try:
            model.predict(X.iloc[:1])
        except Exception:
            model.fit(X, y)

        # Use sklearn permutation_importance via a wrapper
        class _SklearnWrapper:
            def __init__(self, m):
                self._m = m

            def fit(self, X, y):
                return self

            def predict(self, X):
                return self._m.predict(pd.DataFrame(X, columns=feature_cols))

            def score(self, X, y):
                preds = self.predict(X)
                return f1_score(y, preds, average="weighted", zero_division=0)

        feature_cols = list(X.columns)
        wrapper = _SklearnWrapper(model)

        result = permutation_importance(
            wrapper,
            X.values,
            y.values,
            n_repeats=5,
            random_state=42,
            scoring=lambda est, Xv, yv: f1_score(
                yv, est.predict(Xv), average="weighted", zero_division=0
            ),
        )
        imp_vals = result.importances_mean
        # Clip negatives to 0 (noise)
        imp_vals = np.clip(imp_vals, 0, None)
        return pd.Series(imp_vals, index=feature_cols, name="importance").sort_values(
            ascending=False
        )

    raise ValueError(f"Unknown method '{method}'. Use 'permutation' or 'model'.")


def remove_low_importance_features(
    X: pd.DataFrame,
    importance: pd.Series,
    threshold: float = 0.001,
) -> pd.DataFrame:
    """Drop features whose importance is below *threshold*.

    Args:
        X: Feature DataFrame.
        importance: pd.Series of feature importances (index = feature names).
        threshold: Minimum importance to keep.

    Returns:
        Filtered DataFrame with low-importance columns removed.
    """
    keep = importance[importance >= threshold].index.tolist()
    # Always keep columns that appear in X
    keep = [c for c in keep if c in X.columns]
    if not keep:
        # Safety: return at least the top feature
        top = importance.index[0] if len(importance) > 0 else X.columns[0]
        keep = [top]
    return X[keep]


def remove_correlated_features(
    X: pd.DataFrame,
    threshold: float = 0.95,
) -> pd.DataFrame:
    """Drop one of each pair of features whose absolute correlation exceeds *threshold*.

    Strategy: for each correlated pair, drop the feature that appears later in
    column order (i.e. keep the first occurrence).

    Args:
        X: Feature DataFrame.
        threshold: Absolute correlation above which one feature is removed.

    Returns:
        DataFrame with highly correlated duplicate features removed.
    """
    corr = X.corr().abs()
    # Upper triangle mask
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = [col for col in upper.columns if any(upper[col] > threshold)]
    return X.drop(columns=to_drop)


def select_features(
    X: pd.DataFrame,
    y: pd.Series,
    model: BaseModel,
    top_n: int = 20,
) -> pd.DataFrame:
    """Select top N features by model importance after fitting on X, y.

    Steps:
      1. Fit model on X, y.
      2. Compute feature importance (model method first, then permutation).
      3. Return X filtered to the top_n features.

    Args:
        X: Feature DataFrame.
        y: Label Series.
        model: A BaseModel instance (will be fitted in-place).
        top_n: Number of top features to retain.

    Returns:
        Filtered DataFrame with at most top_n columns.
    """
    model.fit(X, y)

    # Try built-in importance first (faster)
    imp = model.feature_importance()
    if imp is None:
        imp = compute_feature_importance(model, X, y, method="permutation")

    top_features = imp.head(top_n).index.tolist()
    top_features = [f for f in top_features if f in X.columns]
    return X[top_features]


def cross_validated_feature_importance(
    model: BaseModel,
    X: pd.DataFrame,
    y: pd.Series,
    cv: int = 5,
) -> pd.Series:
    """Compute stable feature importance estimates via time-series CV.

    For each CV fold, fits a fresh model and collects feature importances.
    Returns the mean importance across folds.

    Args:
        model: A BaseModel instance (template; cloned per fold via get_params).
        X: Feature DataFrame.
        y: Label Series.
        cv: Number of time-series CV splits.

    Returns:
        pd.Series of mean importances sorted descending.
    """
    tscv = TimeSeriesSplit(n_splits=cv)
    all_importances: list = []

    for train_idx, _ in tscv.split(X):
        X_tr = X.iloc[train_idx]
        y_tr = y.iloc[train_idx]

        if len(y_tr.unique()) < 2:
            continue

        # Clone model
        fold_model = model.__class__(**model.get_params())
        fold_model.fit(X_tr, y_tr)

        imp = fold_model.feature_importance()
        if imp is not None:
            all_importances.append(imp)

    if not all_importances:
        # Fall back to single fit
        model.fit(X, y)
        imp = model.feature_importance()
        return imp if imp is not None else pd.Series(dtype=float)

    # Align on common index and average
    combined = pd.concat(all_importances, axis=1).fillna(0.0)
    mean_imp = combined.mean(axis=1)
    return mean_imp.sort_values(ascending=False).rename("importance")
