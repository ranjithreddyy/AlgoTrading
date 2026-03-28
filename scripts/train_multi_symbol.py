#!/usr/bin/env python
"""Multi-symbol training: pooled vs per-symbol comparison.

Symbols: RELIANCE, TCS, HDFCBANK, INFY, ICICIBANK,
         SBIN, HINDUNILVR, BHARTIARTL, KOTAKBANK, LT

Approach:
  1. Pool all data → train single model
  2. Train per-symbol models
  3. Compare pooled vs per-symbol walk-forward F1
"""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from src.features.compute import compute_features
from src.models.baselines import LogisticRegressionModel, RandomForestModel
from src.models.tree_models import CatBoostModel, LightGBMModel, XGBoostModel
from src.research.train import LABEL_REGISTRY, TrainingPipeline

# ------------------------------------------------------------------ #
# Configuration                                                        #
# ------------------------------------------------------------------ #

SYMBOLS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "SBIN", "HINDUNILVR", "BHARTIARTL", "KOTAKBANK", "LT",
]

LABEL_NAME = "binary_5d"      # default label for all comparisons
TRAIN_DAYS = 250
TEST_DAYS = 50
N_SPLITS = 3


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def load_symbol(symbol: str, interval: str = "day") -> pd.DataFrame | None:
    data_dir = ROOT / "data" / "market" / "NSE" / symbol / interval
    csvs = sorted(data_dir.glob("*.csv"))
    if not csvs:
        print(f"  [WARN] No data for {symbol}")
        return None
    csv_path = max(csvs, key=lambda p: p.stat().st_size)
    df = pd.read_csv(csv_path, parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["symbol"] = symbol
    return df


def _default_models():
    return {
        "LogReg": LogisticRegressionModel(),
        "RandomForest": RandomForestModel(),
        "CatBoost": CatBoostModel(),
        "LightGBM": LightGBMModel(),
        "XGBoost": XGBoostModel(),
    }


def evaluate_model(model, df: pd.DataFrame, label_fn) -> dict:
    """Walk-forward evaluate a single model on df."""
    pipe = TrainingPipeline(model)
    try:
        res = pipe.train_and_evaluate(
            df, label_fn=label_fn, label_params={},
            train_days=TRAIN_DAYS, test_days=TEST_DAYS, n_splits=N_SPLITS,
        )
        return res
    except Exception as exc:
        return {"error": str(exc), "folds": [], "aggregate": {}}


def get_mean_f1(res: dict) -> float:
    return res.get("aggregate", {}).get("mean_f1") or 0.0


def print_header(title: str):
    print(f"\n{'='*68}")
    print(f"  {title}")
    print(f"{'='*68}")


def print_model_row(model_name: str, res: dict):
    agg = res.get("aggregate", {})
    if not agg:
        err = res.get("error", "N/A")[:45]
        print(f"  {model_name:<16} ERROR: {err}")
        return
    f1 = agg.get("mean_f1") or 0
    acc = agg.get("mean_accuracy") or 0
    prec = agg.get("mean_precision") or 0
    rec = agg.get("mean_recall") or 0
    n = agg.get("n_folds", 0)
    print(f"  {model_name:<16} {f1:>7.4f} {acc:>7.4f} {prec:>7.4f} {rec:>7.4f} {n:>6}")


def print_results_table(results: dict, title: str = ""):
    if title:
        print(f"\n  {title}")
    header = f"  {'Model':<16} {'F1':>7} {'Acc':>7} {'Prec':>7} {'Rec':>7} {'Folds':>6}"
    print(f"  {'─'*56}")
    print(header)
    print(f"  {'─'*56}")
    for name, res in results.items():
        print_model_row(name, res)
    print(f"  {'─'*56}")


# ------------------------------------------------------------------ #
# Main                                                                 #
# ------------------------------------------------------------------ #

def main():
    label_fn = LABEL_REGISTRY[LABEL_NAME]

    print_header(f"MULTI-SYMBOL TRAINING  |  label={LABEL_NAME}")
    print(f"  Symbols ({len(SYMBOLS)}): {', '.join(SYMBOLS)}")
    print(f"  Train={TRAIN_DAYS} | Test={TEST_DAYS} | Splits={N_SPLITS}")

    # ── Load all data ─────────────────────────────────────────────────
    print("\n  Loading data...")
    symbol_dfs: dict[str, pd.DataFrame] = {}
    for sym in SYMBOLS:
        df = load_symbol(sym)
        if df is not None and len(df) > TRAIN_DAYS + TEST_DAYS:
            symbol_dfs[sym] = df
            print(f"  {sym:<14} {len(df)} bars")
        else:
            if df is not None:
                print(f"  {sym:<14} {len(df)} bars  [WARN: too short, skipped]")

    loaded_syms = list(symbol_dfs.keys())
    print(f"\n  Loaded {len(loaded_syms)} symbols: {', '.join(loaded_syms)}")

    if not loaded_syms:
        print("  ERROR: No data loaded. Exiting.")
        sys.exit(1)

    # ── Per-symbol evaluation ─────────────────────────────────────────
    print_header("PER-SYMBOL MODEL EVALUATION")

    per_symbol_results: dict[str, dict[str, dict]] = {}  # sym -> model -> res
    per_symbol_best: dict[str, tuple] = {}               # sym -> (model_name, f1)

    for sym in loaded_syms:
        df = symbol_dfs[sym]
        print(f"\n  Symbol: {sym}  ({len(df)} bars)")
        sym_results = {}
        for mname, model in _default_models().items():
            res = evaluate_model(model, df, label_fn)
            sym_results[mname] = res
        print_results_table(sym_results)
        per_symbol_results[sym] = sym_results

        # Best model for this symbol
        best_m = max(sym_results, key=lambda n: get_mean_f1(sym_results[n]))
        per_symbol_best[sym] = (best_m, get_mean_f1(sym_results[best_m]))
        print(f"  → Best: {best_m}  F1={per_symbol_best[sym][1]:.4f}")

    # ── Pooled training ───────────────────────────────────────────────
    print_header("POOLED MODEL EVALUATION")
    print("  Concatenating all symbol data (with symbol column)...")

    # Stack raw dataframes; features are computed inside TrainingPipeline
    all_dfs = []
    for sym, df in symbol_dfs.items():
        all_dfs.append(df)
    pooled_df = pd.concat(all_dfs, ignore_index=True)
    # Sort by date so walk-forward is time-ordered
    pooled_df = pooled_df.sort_values("date").reset_index(drop=True)
    print(f"  Pooled dataset: {len(pooled_df)} bars across {len(loaded_syms)} symbols")

    pooled_results: dict[str, dict] = {}
    for mname, model in _default_models().items():
        print(f"  Training {mname} on pooled data...")
        res = evaluate_model(model, pooled_df, label_fn)
        pooled_results[mname] = res

    print_results_table(pooled_results, "Pooled results:")
    best_pooled = max(pooled_results, key=lambda n: get_mean_f1(pooled_results[n]))
    best_pooled_f1 = get_mean_f1(pooled_results[best_pooled])
    print(f"  → Best pooled: {best_pooled}  F1={best_pooled_f1:.4f}")

    # ── Comparison: pooled vs per-symbol ──────────────────────────────
    print_header("POOLED vs PER-SYMBOL COMPARISON")

    print(f"\n  {'Symbol':<14} {'Best Per-Symbol':>18} {'F1 (per-sym)':>14} "
          f"{'F1 (pooled best)':>18} {'Winner':>10}")
    print(f"  {'─'*76}")

    pooled_wins = 0
    per_sym_wins = 0

    for sym in loaded_syms:
        best_ps_model, best_ps_f1 = per_symbol_best[sym]
        # For per-symbol comparison, use the SAME model class as pooled best on this symbol
        ps_f1_same_model = get_mean_f1(per_symbol_results[sym].get(best_pooled, {}))
        winner = "pooled" if best_pooled_f1 > best_ps_f1 else "per-sym"
        if winner == "pooled":
            pooled_wins += 1
        else:
            per_sym_wins += 1
        print(
            f"  {sym:<14} {best_ps_model:>18} {best_ps_f1:>14.4f} "
            f"{best_pooled_f1:>18.4f} {winner:>10}"
        )

    print(f"  {'─'*76}")
    print(f"\n  Pooled wins: {pooled_wins} / {len(loaded_syms)}")
    print(f"  Per-sym wins: {per_sym_wins} / {len(loaded_syms)}")

    # ── Symbol-level mean F1 ──────────────────────────────────────────
    per_sym_mean_f1 = np.mean([v[1] for v in per_symbol_best.values()])
    print(f"\n  Mean per-symbol best F1 : {per_sym_mean_f1:.4f}")
    print(f"  Pooled best model F1    : {best_pooled_f1:.4f}")

    if best_pooled_f1 > per_sym_mean_f1:
        print("\n  CONCLUSION: Pooled model performs BETTER on average.")
        overall_winner = "pooled"
    else:
        print("\n  CONCLUSION: Per-symbol models perform BETTER on average.")
        overall_winner = "per-symbol"

    # ── Model-level summary across symbols ───────────────────────────
    print_header("MODEL-LEVEL AGGREGATE (per-symbol, mean across symbols)")
    model_agg: dict[str, list] = {m: [] for m in _default_models()}
    for sym in loaded_syms:
        for mname in model_agg:
            f1 = get_mean_f1(per_symbol_results[sym].get(mname, {}))
            if f1 > 0:
                model_agg[mname].append(f1)

    print(f"\n  {'Model':<16} {'Mean F1':>9} {'Std F1':>9} {'Symbols':>9}")
    print(f"  {'─'*46}")
    sorted_models = sorted(model_agg, key=lambda m: np.mean(model_agg[m]) if model_agg[m] else 0, reverse=True)
    for mname in sorted_models:
        vals = model_agg[mname]
        if vals:
            print(f"  {mname:<16} {np.mean(vals):>9.4f} {np.std(vals):>9.4f} {len(vals):>9}")
        else:
            print(f"  {mname:<16}      N/A")

    # ── Final summary ─────────────────────────────────────────────────
    print_header("FINAL SUMMARY")
    print(f"  Label type           : {LABEL_NAME}")
    print(f"  Symbols evaluated    : {len(loaded_syms)}")
    print(f"  Overall winner       : {overall_winner}")
    print(f"  Best pooled model    : {best_pooled}  (F1={best_pooled_f1:.4f})")
    print(f"  Mean per-symbol F1   : {per_sym_mean_f1:.4f}")
    print(f"\n{'='*68}")
    print("  Done.")
    print(f"{'='*68}\n")


if __name__ == "__main__":
    main()
