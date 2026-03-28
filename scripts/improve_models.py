#!/usr/bin/env python
"""Iterative model improvement script.

Pipeline per label type:
  1. Baseline: all 5 models, all features, default params
  2. Remove correlated features (> 0.95)
  3. Select top-20 features by importance
  4. Rerun models on selected features → improvement check
  5. Optuna optimisation of best model (30 trials) → tuned model
  6. Print full comparison table
  7. Save best model
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
)

from src.features.compute import compute_features
from src.models.baselines import LogisticRegressionModel, RandomForestModel
from src.models.model_registry import ModelRegistry
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel
from src.research.feature_selection import (
    cross_validated_feature_importance,
    remove_correlated_features,
)
from src.research.optimize import optimize_catboost, optimize_lightgbm, optimize_xgboost
from src.research.train import LABEL_REGISTRY, TrainingPipeline

# ------------------------------------------------------------------ #
# Configuration                                                        #
# ------------------------------------------------------------------ #

TRAIN_DAYS = 250
TEST_DAYS = 50
N_SPLITS = 3
OPTUNA_TRIALS = 30
TOP_N_FEATURES = 20


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def load_data(symbol: str = "RELIANCE", interval: str = "day") -> pd.DataFrame:
    data_dir = ROOT / "data" / "market" / "NSE" / symbol / interval
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        raise FileNotFoundError(f"No CSV files in {data_dir}")
    csv_path = max(csvs, key=lambda p: p.stat().st_size)
    print(f"  Loading {csv_path.name}")
    df = pd.read_csv(csv_path, parse_dates=["date"])
    return df.sort_values("date").reset_index(drop=True)


def _default_models():
    return {
        "LogReg": LogisticRegressionModel(),
        "RandomForest": RandomForestModel(),
        "CatBoost": CatBoostModel(),
        "LightGBM": LightGBMModel(),
        "XGBoost": XGBoostModel(),
    }


def _compute_metrics(y_true, y_pred, y_proba) -> dict:
    acc = accuracy_score(y_true, y_pred)
    prec = precision_score(y_true, y_pred, average="weighted", zero_division=0)
    rec = recall_score(y_true, y_pred, average="weighted", zero_division=0)
    f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)
    unique_classes = np.unique(y_true)
    auc_pr = None
    if len(unique_classes) == 2:
        try:
            auc_pr = average_precision_score(y_true, y_proba)
        except Exception:
            pass
    return {"accuracy": acc, "f1": f1, "precision": prec, "recall": rec, "auc_pr": auc_pr}


def walk_forward_on_precomputed(
    X: pd.DataFrame,
    y: pd.Series,
    model_cls,
    model_params: dict,
    train_days: int = TRAIN_DAYS,
    test_days: int = TEST_DAYS,
    n_splits: int = N_SPLITS,
) -> dict:
    """Walk-forward evaluation using a pre-computed (X, y) pair.

    Returns dict with ``aggregate`` containing mean metrics and ``n_folds``.
    """
    total = len(X)
    max_splits = (total - train_days) // test_days
    if max_splits < 1:
        return {"error": "not enough data", "folds": [], "aggregate": {}}

    actual_splits = min(n_splits, max_splits)
    fold_metrics = []
    start = 0

    for _ in range(actual_splits):
        train_end = start + train_days
        test_end = train_end + test_days
        if test_end > total:
            break

        X_tr = X.iloc[start:train_end]
        y_tr = y.iloc[start:train_end]
        X_te = X.iloc[train_end:test_end]
        y_te = y.iloc[train_end:test_end]

        if len(y_tr.unique()) < 2:
            start += test_days
            continue

        model = model_cls(**model_params)
        model.fit(X_tr, y_tr)
        y_pred = model.predict(X_te)
        y_proba = model.predict_proba(X_te)
        pos_proba = y_proba[:, -1] if y_proba.ndim == 2 else y_proba

        fold_metrics.append(_compute_metrics(y_te.values, y_pred, pos_proba))
        start += test_days

    if not fold_metrics:
        return {"error": "no valid folds", "folds": [], "aggregate": {}}

    keys = ["accuracy", "f1", "precision", "recall"]
    agg = {"n_folds": len(fold_metrics)}
    for k in keys:
        vals = [m[k] for m in fold_metrics]
        agg[f"mean_{k}"] = round(float(np.mean(vals)), 4)
    auc_vals = [m["auc_pr"] for m in fold_metrics if m["auc_pr"] is not None]
    agg["mean_auc_pr"] = round(float(np.mean(auc_vals)), 4) if auc_vals else None
    return {"folds": fold_metrics, "aggregate": agg}


def run_all_models_precomputed(X: pd.DataFrame, y: pd.Series) -> dict:
    """Run all 5 models on pre-computed (X, y). Returns results dict."""
    models_info = {
        "LogReg": (LogisticRegressionModel, LogisticRegressionModel().get_params()),
        "RandomForest": (RandomForestModel, RandomForestModel().get_params()),
        "CatBoost": (CatBoostModel, CatBoostModel().get_params()),
        "LightGBM": (LightGBMModel, LightGBMModel().get_params()),
        "XGBoost": (XGBoostModel, XGBoostModel().get_params()),
    }
    results = {}
    for name, (cls, params) in models_info.items():
        try:
            res = walk_forward_on_precomputed(X, y, cls, params)
            results[name] = res
        except Exception as exc:
            results[name] = {"error": str(exc), "folds": [], "aggregate": {}}
    return results


def mean_f1(results: dict, model_name: str) -> float:
    agg = results.get(model_name, {}).get("aggregate", {})
    return agg.get("mean_f1") or 0.0


def best_model_name(results: dict) -> str:
    return max(results, key=lambda n: mean_f1(results, n))


def print_comparison(label: str, stage: str, results: dict):
    header = f"  {'Model':<14} {'Acc':>7} {'F1':>7} {'AUC-PR':>8} {'Folds':>6}"
    sep = "  " + "─" * 48
    print(f"\n  [{label} | {stage}]")
    print(sep)
    print(header)
    print(sep)
    for name, res in results.items():
        agg = res.get("aggregate", {})
        if not agg:
            err = res.get("error", "N/A")[:40]
            print(f"  {name:<14} ERROR: {err}")
            continue
        acc = agg.get("mean_accuracy") or agg.get("mean_accuracy") or 0
        # handle both key styles
        acc = agg.get("mean_accuracy", agg.get("mean_accuracy", 0)) or 0
        f1 = agg.get("mean_f1") or 0
        auc = agg.get("mean_auc_pr")
        n = agg.get("n_folds", 0)
        auc_s = f"{auc:.4f}" if auc is not None else "   N/A"
        print(f"  {name:<14} {acc:>7.4f} {f1:>7.4f} {auc_s:>8} {n:>6}")
    print(sep)


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main():
    print("=" * 65)
    print("  ITERATIVE MODEL IMPROVEMENT  –  RELIANCE daily")
    print("=" * 65)

    df = load_data("RELIANCE", "day")
    print(f"  Loaded {len(df)} bars\n")

    # Pre-compute full feature matrix once
    print("  Computing features...")
    X_full = compute_features(df)
    print(f"  Feature matrix: {X_full.shape[0]} rows × {X_full.shape[1]} features")

    # Summary table rows
    summary_rows = []

    for label_name in LABEL_REGISTRY:
        label_fn = LABEL_REGISTRY[label_name]

        print(f"\n{'='*65}")
        print(f"  LABEL: {label_name}")
        print(f"{'='*65}")

        # Align X and y
        y_raw = label_fn(df)
        common = X_full.index.intersection(y_raw.index)
        X_aligned = X_full.loc[common].dropna()
        y_aligned = y_raw.loc[X_aligned.index].dropna()
        X_aligned = X_aligned.loc[y_aligned.index]
        print(f"  Dataset: {len(X_aligned)} samples × {X_aligned.shape[1]} features")

        # ── STAGE 1: Baseline (all features, default params) ──────────
        print("\n  [Stage 1] Baseline – all features, default params")
        t0 = time.time()
        base_results = run_all_models_precomputed(X_aligned, y_aligned)
        print_comparison(label_name, "Baseline", base_results)
        best_base = best_model_name(base_results)
        best_base_f1 = mean_f1(base_results, best_base)
        print(f"  → Best baseline: {best_base}  F1={best_base_f1:.4f}  ({time.time()-t0:.1f}s)")

        for name, res in base_results.items():
            agg = res.get("aggregate", {})
            summary_rows.append({
                "label": label_name,
                "model": name,
                "stage": "baseline",
                "mean_f1": agg.get("mean_f1"),
                "mean_accuracy": agg.get("mean_accuracy"),
            })

        # ── STAGE 2: Remove correlated features ───────────────────────
        print("\n  [Stage 2] Remove correlated features (threshold=0.95)")
        X_uncorr = remove_correlated_features(X_aligned, threshold=0.95)
        n_dropped = X_aligned.shape[1] - X_uncorr.shape[1]
        print(f"  Dropped {n_dropped} correlated features → {X_uncorr.shape[1]} remain")

        # ── STAGE 3: Feature selection (top 20 by importance) ─────────
        print(f"\n  [Stage 3] Feature selection – top {TOP_N_FEATURES} by CV importance")
        t0 = time.time()
        rf = RandomForestModel()
        importance = cross_validated_feature_importance(rf, X_uncorr, y_aligned, cv=3)
        top_features = [f for f in importance.head(TOP_N_FEATURES).index if f in X_uncorr.columns]
        X_sel = X_uncorr[top_features]
        print(f"  Selected {len(top_features)} features: {top_features[:5]} ...")
        print(f"  ({time.time()-t0:.1f}s)")

        # ── STAGE 4: Rerun models on selected features ─────────────────
        print("\n  [Stage 4] Models on selected features")
        t0 = time.time()
        sel_results = run_all_models_precomputed(X_sel, y_aligned)
        print_comparison(label_name, "Selected features", sel_results)
        best_sel = best_model_name(sel_results)
        best_sel_f1 = mean_f1(sel_results, best_sel)
        improvement = best_sel_f1 - best_base_f1
        print(f"  → Best selected: {best_sel}  F1={best_sel_f1:.4f}  "
              f"(Δ {improvement:+.4f})  ({time.time()-t0:.1f}s)")

        for name, res in sel_results.items():
            agg = res.get("aggregate", {})
            summary_rows.append({
                "label": label_name,
                "model": name,
                "stage": "selected_features",
                "mean_f1": agg.get("mean_f1"),
                "mean_accuracy": agg.get("mean_accuracy"),
            })

        # ── STAGE 5: Optuna on best tree model ────────────────────────
        opt_model_map = {
            "CatBoost": (CatBoostModel, optimize_catboost),
            "LightGBM": (LightGBMModel, optimize_lightgbm),
            "XGBoost": (XGBoostModel, optimize_xgboost),
        }

        # Choose tree model to optimise: best_sel if it's a tree, otherwise best tree
        optuna_target = best_sel if best_sel in opt_model_map else None
        if optuna_target is None:
            # Pick the best tree model from selected-features results
            tree_candidates = {k: v for k, v in sel_results.items() if k in opt_model_map}
            if tree_candidates:
                optuna_target = max(tree_candidates, key=lambda n: mean_f1(sel_results, n))

        print(f"\n  [Stage 5] Optuna optimisation – {optuna_target} ({OPTUNA_TRIALS} trials)")

        n = len(X_sel)
        split = int(n * 0.8)
        X_tr, X_val = X_sel.iloc[:split], X_sel.iloc[split:]
        y_tr, y_val = y_aligned.iloc[:split], y_aligned.iloc[split:]

        if optuna_target and len(y_tr.unique()) >= 2:
            t0 = time.time()
            model_cls, opt_fn = opt_model_map[optuna_target]
            try:
                opt_out = opt_fn(X_tr, y_tr, X_val, y_val, n_trials=OPTUNA_TRIALS)
                best_params = opt_out["best_params"]
                best_opt_score = opt_out["best_score"]
                print(f"  Optuna best val F1 : {best_opt_score:.4f}  ({time.time()-t0:.1f}s)")
                print(f"  Best params        : {best_params}")

                tuned_res = walk_forward_on_precomputed(
                    X_sel, y_aligned, model_cls, best_params
                )
                tuned_f1 = tuned_res.get("aggregate", {}).get("mean_f1") or 0.0
                print(f"  Tuned walk-fwd F1  : {tuned_f1:.4f}")
                print_comparison(label_name, "Tuned", {optuna_target + "_tuned": tuned_res})

                summary_rows.append({
                    "label": label_name,
                    "model": optuna_target + "_tuned",
                    "stage": "optuna_tuned",
                    "mean_f1": tuned_f1,
                    "mean_accuracy": tuned_res.get("aggregate", {}).get("mean_accuracy"),
                })

                # Save if improvement over baseline
                if tuned_f1 > best_base_f1:
                    print(f"\n  Saving tuned {optuna_target} "
                          f"(F1={tuned_f1:.4f} > baseline {best_base_f1:.4f})")
                    final_model = model_cls(**best_params)
                    final_model.fit(X_sel, y_aligned)
                    registry = ModelRegistry()
                    meta = {
                        "symbol": "RELIANCE",
                        "interval": "day",
                        "label": label_name,
                        "features": top_features,
                        "optuna_params": best_params,
                        "mean_f1_wf": tuned_f1,
                    }
                    version = registry.register(optuna_target, final_model, meta)
                    print(f"  Saved: artifacts/models/{optuna_target}/{version}/")

            except Exception as exc:
                print(f"  Optuna failed: {exc}")
        else:
            print(f"  (Skipping – insufficient classes or no tree model available)")

    # ── Full summary table ─────────────────────────────────────────────
    print(f"\n{'='*65}")
    print("  FULL COMPARISON SUMMARY")
    print(f"{'='*65}")
    summary_df = pd.DataFrame(summary_rows)
    if not summary_df.empty:
        summary_df = summary_df.sort_values(
            ["label", "mean_f1"], ascending=[True, False]
        ).reset_index(drop=True)

        for label_name, group in summary_df.groupby("label", sort=False):
            print(f"\n  Label: {label_name}")
            print(f"  {'Stage':<22} {'Model':<20} {'F1':>7} {'Acc':>7}")
            print(f"  {'─'*58}")
            for _, row in group.iterrows():
                f1_s = f"{row['mean_f1']:.4f}" if pd.notna(row["mean_f1"]) else "  N/A"
                acc_s = (
                    f"{row['mean_accuracy']:.4f}"
                    if pd.notna(row.get("mean_accuracy"))
                    else "  N/A"
                )
                print(f"  {row['stage']:<22} {row['model']:<20} {f1_s:>7} {acc_s:>7}")

    valid_summary = summary_df.dropna(subset=["mean_f1"])
    if not valid_summary.empty:
        best_idx = valid_summary["mean_f1"].idxmax()
        best_row = valid_summary.loc[best_idx]
        print(
            f"\n  *** BEST OVERALL: [{best_row['label']}] {best_row['model']} "
            f"({best_row['stage']}) F1={best_row['mean_f1']:.4f} ***"
        )

    print(f"\n{'='*65}")
    print("  Done.")
    print(f"{'='*65}\n")


if __name__ == "__main__":
    main()
