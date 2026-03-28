"""Optuna-based hyperparameter optimization for ML models."""

from typing import Any, Dict, List, Optional, Tuple, Type

import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import f1_score, accuracy_score, average_precision_score
from sklearn.model_selection import TimeSeriesSplit

from src.models.baselines import BaseModel
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel

# Silence Optuna INFO logs
optuna.logging.set_verbosity(optuna.logging.WARNING)


# ------------------------------------------------------------------
# Parameter search spaces
# ------------------------------------------------------------------
_PARAM_SPACES: Dict[str, Any] = {
    "CatBoostModel": {
        "iterations": ("int", 100, 1000),
        "depth": ("int", 4, 10),
        "learning_rate": ("log_float", 0.005, 0.3),
        "l2_leaf_reg": ("log_float", 1.0, 10.0),
        "bagging_temperature": ("float", 0.0, 1.0),
    },
    "LightGBMModel": {
        "n_estimators": ("int", 100, 1000),
        "max_depth": ("int", 3, 10),
        "learning_rate": ("log_float", 0.005, 0.3),
        "num_leaves": ("int", 15, 127),
        "min_child_samples": ("int", 5, 100),
        "subsample": ("float", 0.5, 1.0),
        "colsample_bytree": ("float", 0.5, 1.0),
        "reg_alpha": ("log_float", 1e-3, 10.0),
        "reg_lambda": ("log_float", 1e-3, 10.0),
    },
    "XGBoostModel": {
        "n_estimators": ("int", 100, 1000),
        "max_depth": ("int", 3, 10),
        "learning_rate": ("log_float", 0.005, 0.3),
        "min_child_weight": ("int", 1, 20),
        "subsample": ("float", 0.5, 1.0),
        "colsample_bytree": ("float", 0.5, 1.0),
        "reg_alpha": ("log_float", 1e-3, 10.0),
        "reg_lambda": ("log_float", 1e-3, 10.0),
        "gamma": ("float", 0.0, 5.0),
    },
}


def _sample_param(trial: optuna.Trial, name: str, spec: tuple):
    kind = spec[0]
    if kind == "int":
        return trial.suggest_int(name, spec[1], spec[2])
    elif kind == "float":
        return trial.suggest_float(name, spec[1], spec[2])
    elif kind == "log_float":
        return trial.suggest_float(name, spec[1], spec[2], log=True)
    raise ValueError(f"Unknown param type: {kind}")


_METRIC_FNS = {
    "f1": lambda y, p, _: f1_score(y, p, average="weighted", zero_division=0),
    "accuracy": lambda y, p, _: accuracy_score(y, p),
    "auc_pr": lambda y, _, prob: average_precision_score(y, prob),
}


class HyperOptimizer:
    """Optuna-driven hyperparameter search."""

    def optimize(
        self,
        model_class: Type[BaseModel],
        X: pd.DataFrame,
        y: pd.Series,
        n_trials: int = 50,
        metric: str = "f1",
        n_cv_splits: int = 3,
    ) -> Dict[str, Any]:
        """Search hyperparameters using time-series cross-validation.

        Returns dict with ``best_params``, ``best_score``, ``trials`` history.
        """
        class_name = model_class.__name__
        if class_name not in _PARAM_SPACES:
            raise ValueError(
                f"No parameter space defined for {class_name}. "
                f"Supported: {list(_PARAM_SPACES.keys())}"
            )

        space = _PARAM_SPACES[class_name]
        score_fn = _METRIC_FNS.get(metric)
        if score_fn is None:
            raise ValueError(f"Unsupported metric '{metric}'. Choose from {list(_METRIC_FNS.keys())}")

        X_arr = X.values
        y_arr = y.values

        tscv = TimeSeriesSplit(n_splits=n_cv_splits)

        def objective(trial: optuna.Trial) -> float:
            params = {k: _sample_param(trial, k, v) for k, v in space.items()}
            scores: List[float] = []

            for train_idx, val_idx in tscv.split(X_arr):
                X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
                y_tr, y_val = y.iloc[train_idx], y.iloc[val_idx]

                if len(y_tr.unique()) < 2:
                    continue

                model = model_class(**params)
                model.fit(X_tr, y_tr)
                preds = model.predict(X_val)
                probas = model.predict_proba(X_val)
                pos_prob = probas[:, -1] if probas.ndim == 2 else probas

                scores.append(score_fn(y_val.values, preds, pos_prob))

            return float(np.mean(scores)) if scores else 0.0

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

        trials_history = [
            {"number": t.number, "value": t.value, "params": t.params}
            for t in study.trials
        ]

        return {
            "best_params": study.best_params,
            "best_score": study.best_value,
            "trials": trials_history,
        }


# ------------------------------------------------------------------
# Convenience wrappers: train/val split API
# ------------------------------------------------------------------

def _optimize_with_val(
    model_class: Type[BaseModel],
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 30,
) -> Dict[str, Any]:
    """Internal: run Optuna optimization evaluating on a fixed validation split.

    Args:
        model_class: One of CatBoostModel, LightGBMModel, XGBoostModel.
        X_train: Training features.
        y_train: Training labels.
        X_val: Validation features.
        y_val: Validation labels.
        n_trials: Number of Optuna trials.

    Returns:
        Dict with keys ``best_params`` and ``best_score``.
    """
    class_name = model_class.__name__
    if class_name not in _PARAM_SPACES:
        raise ValueError(
            f"No parameter space defined for {class_name}. "
            f"Supported: {list(_PARAM_SPACES.keys())}"
        )

    space = _PARAM_SPACES[class_name]

    def objective(trial: optuna.Trial) -> float:
        params = {k: _sample_param(trial, k, v) for k, v in space.items()}
        if len(y_train.unique()) < 2:
            return 0.0
        model = model_class(**params)
        model.fit(X_train, y_train)
        preds = model.predict(X_val)
        return float(f1_score(y_val.values, preds, average="weighted", zero_division=0))

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)
    return {"best_params": study.best_params, "best_score": study.best_value}


def optimize_catboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 30,
) -> Dict[str, Any]:
    """Run Optuna hyperparameter search for CatBoost.

    Args:
        X_train: Training features.
        y_train: Training labels.
        X_val: Validation features.
        y_val: Validation labels.
        n_trials: Number of Optuna trials.

    Returns:
        Dict with ``best_params`` (dict) and ``best_score`` (float).
    """
    return _optimize_with_val(CatBoostModel, X_train, y_train, X_val, y_val, n_trials)


def optimize_lightgbm(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 30,
) -> Dict[str, Any]:
    """Run Optuna hyperparameter search for LightGBM.

    Args:
        X_train: Training features.
        y_train: Training labels.
        X_val: Validation features.
        y_val: Validation labels.
        n_trials: Number of Optuna trials.

    Returns:
        Dict with ``best_params`` (dict) and ``best_score`` (float).
    """
    return _optimize_with_val(LightGBMModel, X_train, y_train, X_val, y_val, n_trials)


def optimize_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    n_trials: int = 30,
) -> Dict[str, Any]:
    """Run Optuna hyperparameter search for XGBoost.

    Args:
        X_train: Training features.
        y_train: Training labels.
        X_val: Validation features.
        y_val: Validation labels.
        n_trials: Number of Optuna trials.

    Returns:
        Dict with ``best_params`` (dict) and ``best_score`` (float).
    """
    return _optimize_with_val(XGBoostModel, X_train, y_train, X_val, y_val, n_trials)
