"""Post-trade execution quality analytics."""

from typing import Any, Dict, List, Optional

import numpy as np


def implementation_shortfall(fill_price: float, signal_price: float) -> float:
    """Measure how much the fill deviates from the signal (decision) price.

    A positive value means the fill was worse than the signal price
    (bought higher or sold lower).

    Args:
        fill_price: Actual execution price.
        signal_price: Price at the time the signal was generated.

    Returns:
        Shortfall as a fraction of signal price (e.g. 0.001 = 10 bps).
    """
    if signal_price == 0:
        return 0.0
    return (fill_price - signal_price) / signal_price


def fill_vs_vwap(fill_price: float, vwap: float) -> float:
    """Compare fill price to the VWAP of the execution window.

    Positive means filled above VWAP (bad for buys, good for sells).

    Args:
        fill_price: Actual execution price.
        vwap: Volume-weighted average price for the same period.

    Returns:
        Deviation as a fraction of VWAP.
    """
    if vwap == 0:
        return 0.0
    return (fill_price - vwap) / vwap


def slippage_analysis(
    trades: List[Dict[str, Any]],
    expected_slippage: float = 0.001,
) -> Dict[str, Any]:
    """Analyse actual slippage against the modelled expectation.

    Each trade dict should have at least:
        - fill_price: actual fill
        - expected_price: price used in the backtest / signal
    Optionally:
        - side: 'buy' or 'sell' (affects sign interpretation)

    Args:
        trades: List of trade dicts.
        expected_slippage: Model's assumed slippage fraction.

    Returns:
        Dict with slippage statistics.
    """
    if not trades:
        return {
            "n_trades": 0,
            "avg_slippage": 0.0,
            "max_slippage": 0.0,
            "min_slippage": 0.0,
            "std_slippage": 0.0,
            "pct_exceeding_2x_model": 0.0,
        }

    slippages = []
    for t in trades:
        fill = t["fill_price"]
        expected = t["expected_price"]
        if expected == 0:
            continue
        slip = abs(fill - expected) / expected
        slippages.append(slip)

    if not slippages:
        return {
            "n_trades": len(trades),
            "avg_slippage": 0.0,
            "max_slippage": 0.0,
            "min_slippage": 0.0,
            "std_slippage": 0.0,
            "pct_exceeding_2x_model": 0.0,
        }

    arr = np.array(slippages)
    exceeding = np.sum(arr > 2 * expected_slippage)

    return {
        "n_trades": len(trades),
        "avg_slippage": float(np.mean(arr)),
        "max_slippage": float(np.max(arr)),
        "min_slippage": float(np.min(arr)),
        "std_slippage": float(np.std(arr)),
        "pct_exceeding_2x_model": float(exceeding / len(arr) * 100),
    }


def generate_execution_report(
    trades: List[Dict[str, Any]],
    expected_slippage: float = 0.001,
) -> Dict[str, Any]:
    """Generate a comprehensive execution quality report.

    Each trade dict should have:
        - fill_price
        - expected_price (signal/decision price)
    Optionally:
        - vwap (for fill-vs-VWAP analysis)
        - fill_timestamp, signal_timestamp (for latency)

    Args:
        trades: List of trade dicts.
        expected_slippage: Model's assumed slippage fraction.

    Returns:
        Dict with execution quality metrics.
    """
    report: Dict[str, Any] = {}

    # Slippage analysis
    slip = slippage_analysis(trades, expected_slippage)
    report["n_trades"] = slip["n_trades"]
    report["avg_slippage"] = slip["avg_slippage"]
    report["max_slippage"] = slip["max_slippage"]
    report["slippage_distribution"] = {
        "min": slip["min_slippage"],
        "mean": slip["avg_slippage"],
        "max": slip["max_slippage"],
        "std": slip["std_slippage"],
    }
    report["pct_trades_exceeding_2x_model"] = slip["pct_exceeding_2x_model"]

    # Implementation shortfall
    shortfalls = []
    for t in trades:
        if t.get("expected_price", 0) != 0:
            shortfalls.append(
                implementation_shortfall(t["fill_price"], t["expected_price"])
            )
    if shortfalls:
        report["avg_implementation_shortfall"] = float(np.mean(shortfalls))
    else:
        report["avg_implementation_shortfall"] = 0.0

    # Fill vs VWAP (if available)
    vwap_devs = []
    for t in trades:
        if "vwap" in t and t["vwap"] != 0:
            vwap_devs.append(fill_vs_vwap(t["fill_price"], t["vwap"]))
    if vwap_devs:
        report["avg_fill_vs_vwap"] = float(np.mean(vwap_devs))
    else:
        report["avg_fill_vs_vwap"] = None

    # Fill latency stats (if timestamps available)
    latencies = []
    for t in trades:
        if "fill_timestamp" in t and "signal_timestamp" in t:
            dt = (t["fill_timestamp"] - t["signal_timestamp"]).total_seconds()
            latencies.append(dt)
    if latencies:
        arr = np.array(latencies)
        report["fill_latency_stats"] = {
            "mean_seconds": float(np.mean(arr)),
            "median_seconds": float(np.median(arr)),
            "max_seconds": float(np.max(arr)),
            "p95_seconds": float(np.percentile(arr, 95)),
        }
    else:
        report["fill_latency_stats"] = None

    return report
