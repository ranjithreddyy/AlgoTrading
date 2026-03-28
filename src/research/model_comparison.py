"""Model × label comparison utilities."""

from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.models.baselines import BaseModel, LogisticRegressionModel, RandomForestModel
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel
from src.research.train import LABEL_REGISTRY, TrainingPipeline


def _default_models() -> Dict[str, BaseModel]:
    return {
        "LogReg": LogisticRegressionModel(),
        "RandomForest": RandomForestModel(),
        "CatBoost": CatBoostModel(),
        "LightGBM": LightGBMModel(),
        "XGBoost": XGBoostModel(),
    }


def compare_labels(
    df: pd.DataFrame,
    models: Optional[Dict[str, BaseModel]] = None,
    label_types: Optional[List[str]] = None,
    train_days: int = 250,
    test_days: int = 50,
    n_splits: int = 3,
) -> pd.DataFrame:
    """Run all model × label combinations and collect metrics.

    Args:
        df: OHLCV DataFrame.
        models: Dict mapping model name -> BaseModel instance.
                Defaults to all 5 standard models.
        label_types: List of label names from LABEL_REGISTRY.
                     Defaults to all registered label types.
        train_days: Training window size (rows).
        test_days: Test window size (rows).
        n_splits: Walk-forward CV splits.

    Returns:
        DataFrame with columns:
            label, model, mean_f1, mean_accuracy, mean_precision,
            mean_recall, mean_auc_pr, n_folds, error
    """
    if models is None:
        models = _default_models()
    if label_types is None:
        label_types = list(LABEL_REGISTRY.keys())

    rows = []
    for label_name in label_types:
        label_fn = LABEL_REGISTRY.get(label_name)
        if label_fn is None:
            print(f"  [WARN] Unknown label type '{label_name}', skipping.")
            continue

        for model_name, model_instance in models.items():
            # Clone model to avoid state leakage
            model = model_instance.__class__(**model_instance.get_params())
            pipe = TrainingPipeline(model)

            try:
                res = pipe.train_and_evaluate(
                    df,
                    label_fn=label_fn,
                    label_params={},
                    train_days=train_days,
                    test_days=test_days,
                    n_splits=n_splits,
                )
                agg = res.get("aggregate", {})
                rows.append(
                    {
                        "label": label_name,
                        "model": model_name,
                        "mean_f1": agg.get("mean_f1"),
                        "mean_accuracy": agg.get("mean_accuracy"),
                        "mean_precision": agg.get("mean_precision"),
                        "mean_recall": agg.get("mean_recall"),
                        "mean_auc_pr": agg.get("mean_auc_pr"),
                        "n_folds": agg.get("n_folds", 0),
                        "error": None,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "label": label_name,
                        "model": model_name,
                        "mean_f1": None,
                        "mean_accuracy": None,
                        "mean_precision": None,
                        "mean_recall": None,
                        "mean_auc_pr": None,
                        "n_folds": 0,
                        "error": str(exc),
                    }
                )

    results_df = pd.DataFrame(rows)
    if not results_df.empty and "mean_f1" in results_df.columns:
        results_df = results_df.sort_values("mean_f1", ascending=False).reset_index(
            drop=True
        )
    return results_df


def find_best_combination(
    results: pd.DataFrame,
) -> Tuple[str, str, float]:
    """Find the best (model, label) combination by mean F1.

    Args:
        results: DataFrame returned by :func:`compare_labels`.

    Returns:
        Tuple of (best_model, best_label, best_score).
        Returns ('', '', 0.0) if no valid results exist.
    """
    valid = results.dropna(subset=["mean_f1"])
    if valid.empty:
        return ("", "", 0.0)

    best_row = valid.loc[valid["mean_f1"].idxmax()]
    return (
        str(best_row["model"]),
        str(best_row["label"]),
        float(best_row["mean_f1"]),
    )
