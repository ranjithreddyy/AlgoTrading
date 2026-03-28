"""ML training pipeline with walk-forward validation."""

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
)

from src.features.compute import compute_features
from src.labels.horizon_returns import binary_label, forward_returns
from src.labels.triple_barrier import triple_barrier_label
from src.models.baselines import BaseModel, LogisticRegressionModel, RandomForestModel
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel


# ------------------------------------------------------------------
# Built-in label functions (accessible as LABEL_REGISTRY)
# ------------------------------------------------------------------

def _label_binary_5d(df: pd.DataFrame) -> pd.Series:
    """Binary label: 1 if 5-day forward return > 0, else 0."""
    fwd = forward_returns(df, horizons=[5])
    return binary_label(fwd["fwd_ret_5"], threshold=0.0)


def _label_binary_10d(df: pd.DataFrame) -> pd.Series:
    """Binary label: 1 if 10-day forward return > 0, else 0."""
    fwd = forward_returns(df, horizons=[10])
    return binary_label(fwd["fwd_ret_10"], threshold=0.0)


def _label_triple_barrier(df: pd.DataFrame) -> pd.Series:
    """Triple-barrier label mapped to binary (1 if TP hit, else 0).

    Uses TP=3%, SL=2%, max holding=10 bars.
    """
    labels = triple_barrier_label(df, take_profit=0.03, stop_loss=0.02, max_holding=10)
    return (labels == 1).astype(int)


def _label_directional_3(df: pd.DataFrame) -> pd.Series:
    """Directional 3-class label: -1 (down), 0 (flat), +1 (up).

    Uses 5-day forward return with ±0.5% threshold.
    """
    fwd = forward_returns(df, horizons=[5])
    ret = fwd["fwd_ret_5"]
    labels = pd.Series(0, index=ret.index, name="directional_3")
    labels[ret > 0.005] = 1
    labels[ret < -0.005] = -1
    return labels


LABEL_REGISTRY: Dict[str, Callable] = {
    "binary_5d": _label_binary_5d,
    "binary_10d": _label_binary_10d,
    "triple_barrier": _label_triple_barrier,
    "directional_3": _label_directional_3,
}


class TrainingPipeline:
    """End-to-end ML training with walk-forward evaluation."""

    def __init__(self, model: BaseModel, feature_names: Optional[List[str]] = None):
        self.model = model
        self.feature_names = feature_names

    # ------------------------------------------------------------------
    # Dataset preparation
    # ------------------------------------------------------------------
    def prepare_dataset(
        self,
        df: pd.DataFrame,
        label_fn: Callable,
        label_params: Dict[str, Any],
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Compute features and labels, align, and drop NaNs.

        Args:
            df: OHLCV DataFrame.
            label_fn: A callable ``label_fn(df, **label_params) -> Series``.
            label_params: Keyword arguments forwarded to *label_fn*.

        Returns:
            (X, y) with aligned indices and no NaN values.
        """
        features = compute_features(df, self.feature_names)
        labels = label_fn(df, **label_params)

        # Align on common index
        common = features.index.intersection(labels.index)
        X = features.loc[common]
        y = labels.loc[common]

        # Drop any remaining NaN rows
        mask = X.notna().all(axis=1) & y.notna()
        X = X.loc[mask]
        y = y.loc[mask]

        return X, y

    # ------------------------------------------------------------------
    # Walk-forward training & evaluation
    # ------------------------------------------------------------------
    def train_and_evaluate(
        self,
        df: pd.DataFrame,
        label_fn: Callable,
        label_params: Dict[str, Any],
        train_days: int = 300,
        test_days: int = 60,
        n_splits: int = 5,
    ) -> Dict[str, Any]:
        """Walk-forward train/test with per-fold metrics.

        Returns dict with ``folds`` list and ``aggregate`` summary.
        """
        X, y = self.prepare_dataset(df, label_fn, label_params)

        # Ensure enough data; reduce splits if necessary
        total = len(X)
        window = train_days + test_days
        max_splits = (total - train_days) // test_days
        if max_splits < 1:
            raise ValueError(
                f"Not enough data for even 1 fold "
                f"(need {window}, have {total})"
            )
        n_splits = min(n_splits, max_splits)

        fold_results: List[Dict[str, Any]] = []
        start = 0

        for fold_idx in range(n_splits):
            train_end = start + train_days
            test_start = train_end
            test_end = test_start + test_days

            if test_end > total:
                break

            X_train = X.iloc[start:train_end]
            y_train = y.iloc[start:train_end]
            X_test = X.iloc[test_start:test_end]
            y_test = y.iloc[test_start:test_end]

            # Skip fold if only one class in training set
            if len(y_train.unique()) < 2:
                start += test_days
                continue

            # Fresh model per fold (clone params)
            model = self.model.__class__(**self.model.get_params())
            model.fit(X_train, y_train)

            y_pred = model.predict(X_test)
            y_proba = model.predict_proba(X_test)

            # For binary: use probability of positive class
            if y_proba.ndim == 2:
                pos_proba = y_proba[:, -1]
            else:
                pos_proba = y_proba

            metrics = self._compute_metrics(y_test.values, y_pred, pos_proba)
            metrics["fold"] = fold_idx
            fold_results.append(metrics)

            start += test_days

        aggregate = self._aggregate(fold_results) if fold_results else {}
        return {"folds": fold_results, "aggregate": aggregate}

    # ------------------------------------------------------------------
    # Multi-model comparison
    # ------------------------------------------------------------------
    @staticmethod
    def train_all_models(
        df: pd.DataFrame,
        label_fn: Callable,
        label_params: Dict[str, Any],
        feature_names: Optional[List[str]] = None,
        train_days: int = 300,
        test_days: int = 60,
        n_splits: int = 5,
    ) -> Dict[str, Dict[str, Any]]:
        """Train all baseline + tree models and return comparison.

        Returns dict mapping model name -> results dict.
        """
        model_map = {
            "LogReg": LogisticRegressionModel(),
            "RandomForest": RandomForestModel(),
            "CatBoost": CatBoostModel(),
            "LightGBM": LightGBMModel(),
            "XGBoost": XGBoostModel(),
        }

        results: Dict[str, Dict[str, Any]] = {}
        for name, model in model_map.items():
            pipe = TrainingPipeline(model, feature_names)
            try:
                res = pipe.train_and_evaluate(
                    df, label_fn, label_params,
                    train_days=train_days,
                    test_days=test_days,
                    n_splits=n_splits,
                )
                results[name] = res
            except Exception as e:
                results[name] = {"error": str(e), "folds": [], "aggregate": {}}

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray,
    ) -> Dict[str, float]:
        """Compute classification metrics for a single fold."""
        acc = accuracy_score(y_true, y_pred)
        prec = precision_score(y_true, y_pred, average="weighted", zero_division=0)
        rec = recall_score(y_true, y_pred, average="weighted", zero_division=0)
        f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

        # AUC-PR and Brier only meaningful for binary
        unique_classes = np.unique(y_true)
        if len(unique_classes) == 2:
            try:
                auc_pr = average_precision_score(y_true, y_proba)
            except Exception:
                auc_pr = float("nan")
            try:
                brier = brier_score_loss(y_true, y_proba)
            except Exception:
                brier = float("nan")
        else:
            auc_pr = float("nan")
            brier = float("nan")

        return {
            "accuracy": round(acc, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
            "auc_pr": round(auc_pr, 4) if not np.isnan(auc_pr) else None,
            "brier": round(brier, 4) if not np.isnan(brier) else None,
        }

    @staticmethod
    def _aggregate(folds: List[Dict[str, float]]) -> Dict[str, Any]:
        """Average metrics across folds."""
        if not folds:
            return {}
        keys = ["accuracy", "precision", "recall", "f1", "auc_pr", "brier"]
        agg: Dict[str, Any] = {"n_folds": len(folds)}
        for k in keys:
            vals = [f[k] for f in folds if f.get(k) is not None]
            if vals:
                agg[f"mean_{k}"] = round(sum(vals) / len(vals), 4)
                agg[f"std_{k}"] = round(
                    (sum((v - sum(vals) / len(vals)) ** 2 for v in vals) / len(vals)) ** 0.5,
                    4,
                )
            else:
                agg[f"mean_{k}"] = None
                agg[f"std_{k}"] = None
        return agg
