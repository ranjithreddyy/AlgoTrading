#!/usr/bin/env python
"""CLI for training and comparing ML models on market data."""

import argparse
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.features.compute import compute_features
from src.labels.horizon_returns import binary_label, forward_returns
from src.labels.triple_barrier import triple_barrier_label
from src.models.baselines import LogisticRegressionModel, RandomForestModel
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel
from src.models.model_registry import ModelRegistry
from src.research.train import TrainingPipeline
from src.research.optimize import HyperOptimizer


# ------------------------------------------------------------------
# Label functions
# ------------------------------------------------------------------
def _binary_label_fn(df: pd.DataFrame, horizon: int = 5, threshold: float = 0.0, **kw) -> pd.Series:
    """Binary label: 1 if forward return > threshold."""
    fwd = forward_returns(df, horizons=[horizon])
    return binary_label(fwd[f"fwd_ret_{horizon}"], threshold=threshold)


def _triple_barrier_label_fn(
    df: pd.DataFrame,
    take_profit: float = 0.03,
    stop_loss: float = 0.02,
    max_holding: int = 10,
    **kw,
) -> pd.Series:
    """Triple-barrier label mapped to binary (1 if TP hit, else 0)."""
    labels = triple_barrier_label(df, take_profit, stop_loss, max_holding)
    # Map: +1 -> 1, else 0
    return (labels == 1).astype(int)


LABEL_FNS = {
    "binary": (_binary_label_fn, dict(horizon=5, threshold=0.0)),
    "triple_barrier": (_triple_barrier_label_fn, dict(take_profit=0.03, stop_loss=0.02, max_holding=10)),
}

MODEL_MAP = {
    "logreg": ("LogReg", LogisticRegressionModel),
    "rf": ("RandomForest", RandomForestModel),
    "catboost": ("CatBoost", CatBoostModel),
    "lgbm": ("LightGBM", LightGBMModel),
    "xgb": ("XGBoost", XGBoostModel),
}


def _load_data(symbol: str, interval: str) -> pd.DataFrame:
    """Load OHLCV data from the data directory."""
    data_dir = ROOT / "data" / "market" / "NSE" / symbol / interval
    # Prefer the date-range file; fall back to data.csv
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    # Use the largest file (most data)
    csv_path = max(csvs, key=lambda p: p.stat().st_size)
    print(f"Loading data from {csv_path}")
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def _print_comparison(results: dict) -> None:
    """Print a formatted comparison table."""
    header = f"{'Model':<15} {'Acc':>7} {'Prec':>7} {'Recall':>7} {'F1':>7} {'AUC-PR':>7} {'Brier':>7} {'Folds':>6}"
    print("\n" + "=" * len(header))
    print("  WALK-FORWARD OUT-OF-SAMPLE RESULTS")
    print("=" * len(header))
    print(header)
    print("-" * len(header))

    for name, res in results.items():
        agg = res.get("aggregate", {})
        if not agg:
            err = res.get("error", "no results")
            print(f"{name:<15} ERROR: {err}")
            continue
        acc = agg.get("mean_accuracy", 0) or 0
        prec = agg.get("mean_precision", 0) or 0
        rec = agg.get("mean_recall", 0) or 0
        f1 = agg.get("mean_f1", 0) or 0
        auc_pr = agg.get("mean_auc_pr")
        brier = agg.get("mean_brier")
        n = agg.get("n_folds", 0)
        auc_str = f"{auc_pr:.4f}" if auc_pr is not None else "   N/A"
        brier_str = f"{brier:.4f}" if brier is not None else "   N/A"
        print(f"{name:<15} {acc:>7.4f} {prec:>7.4f} {rec:>7.4f} {f1:>7.4f} {auc_str:>7} {brier_str:>7} {n:>6}")

    print("=" * len(header))


def main():
    parser = argparse.ArgumentParser(description="Train ML models on market data")
    parser.add_argument("--symbol", default="RELIANCE", help="Symbol (default: RELIANCE)")
    parser.add_argument("--interval", default="day", help="Bar interval (default: day)")
    parser.add_argument("--model", default="all", choices=["all"] + list(MODEL_MAP.keys()),
                        help="Model to train (default: all)")
    parser.add_argument("--label", default="binary", choices=list(LABEL_FNS.keys()),
                        help="Label type (default: binary)")
    parser.add_argument("--optimize", action="store_true", help="Run Optuna hyperparameter optimization")
    parser.add_argument("--n-trials", type=int, default=50, help="Optuna trials (default: 50)")
    parser.add_argument("--train-days", type=int, default=250, help="Training window size in rows")
    parser.add_argument("--test-days", type=int, default=50, help="Test window size in rows")
    parser.add_argument("--n-splits", type=int, default=3, help="Number of walk-forward splits")
    args = parser.parse_args()

    # Load data
    df = _load_data(args.symbol, args.interval)
    print(f"Loaded {len(df)} bars for {args.symbol} ({args.interval})")

    # Label function
    label_fn, label_params = LABEL_FNS[args.label]
    print(f"Label: {args.label} | params: {label_params}")

    # Select models
    if args.model == "all":
        models_to_train = {name: cls() for _, (name, cls) in MODEL_MAP.items()}
    else:
        name, cls = MODEL_MAP[args.model]
        models_to_train = {name: cls()}

    # Optuna optimization
    if args.optimize:
        print("\n--- Hyperparameter Optimization ---")
        optimizer = HyperOptimizer()
        # Prepare dataset once for optimization
        pipe = TrainingPipeline(list(models_to_train.values())[0])
        X, y = pipe.prepare_dataset(df, label_fn, label_params)
        print(f"Dataset: {X.shape[0]} samples, {X.shape[1]} features")

        opt_classes = {
            "CatBoost": CatBoostModel,
            "LightGBM": LightGBMModel,
            "XGBoost": XGBoostModel,
        }

        for model_name in models_to_train:
            if model_name in opt_classes:
                print(f"\nOptimizing {model_name} ({args.n_trials} trials)...")
                result = optimizer.optimize(
                    opt_classes[model_name], X, y,
                    n_trials=args.n_trials, metric="f1",
                )
                print(f"  Best score: {result['best_score']:.4f}")
                print(f"  Best params: {result['best_params']}")
                # Replace model with optimized version
                models_to_train[model_name] = opt_classes[model_name](**result["best_params"])

    # Walk-forward training
    print("\n--- Walk-Forward Training ---")
    results = {}
    for model_name, model in models_to_train.items():
        print(f"Training {model_name}...")
        pipe = TrainingPipeline(model)
        try:
            res = pipe.train_and_evaluate(
                df, label_fn, label_params,
                train_days=args.train_days,
                test_days=args.test_days,
                n_splits=args.n_splits,
            )
            results[model_name] = res
        except Exception as e:
            print(f"  ERROR: {e}")
            results[model_name] = {"error": str(e), "folds": [], "aggregate": {}}

    _print_comparison(results)

    # Save best model
    registry = ModelRegistry()
    best_name = None
    best_f1 = -1.0
    for model_name, res in results.items():
        agg = res.get("aggregate", {})
        f1_val = agg.get("mean_f1", 0) or 0
        if f1_val > best_f1:
            best_f1 = f1_val
            best_name = model_name

    if best_name and best_f1 > 0:
        # Retrain best model on full data for saving
        best_model = models_to_train[best_name]
        pipe = TrainingPipeline(best_model)
        X, y = pipe.prepare_dataset(df, label_fn, label_params)
        best_model.fit(X, y)

        metadata = {
            "symbol": args.symbol,
            "interval": args.interval,
            "label": args.label,
            "label_params": label_params,
            "features": list(X.columns),
            "train_dates": {"start": str(df["date"].min()), "end": str(df["date"].max())},
            "metrics": results[best_name].get("aggregate", {}),
        }
        version = registry.register(best_name, best_model, metadata)
        print(f"\nBest model: {best_name} (mean F1={best_f1:.4f})")
        print(f"Saved to artifacts/models/{best_name}/{version}/")
    else:
        print("\nNo model achieved positive F1 score.")


if __name__ == "__main__":
    main()
