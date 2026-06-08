#!/usr/bin/env python3
"""
Offline factor validation (alphalens-style IC / quintile spread).

Usage:
  cd backend && python scripts/factor_validation.py --symbols AAPL,MSFT,NVDA --factor momentum_20d
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from data.price_service import PriceService
from scoring.technical import momentum_score, relative_strength_vs_spy, trend_score


def _factor_series(symbol: str, hist: pd.DataFrame, spy: pd.DataFrame, factor: str) -> pd.Series:
    from scoring.openalpha_factors import OPENALPHA_SCORERS, score_openalpha_factor

    rows: list[float] = []
    for i in range(60, len(hist)):
        window = hist.iloc[: i + 1]
        spy_w = spy.iloc[: i + 1] if len(spy) > i else spy
        if factor in OPENALPHA_SCORERS:
            sc = score_openalpha_factor(factor, window, spy_w)
            rows.append(sc if sc is not None else 50.0)
        elif factor == "momentum_20d":
            rows.append(momentum_score(window, days=20))
        elif factor == "trend":
            rows.append(trend_score(window))
        elif factor == "rs_vs_spy":
            rows.append(relative_strength_vs_spy(window, spy_w, days=20))
        else:
            rows.append(momentum_score(window, days=5))
    idx = hist.index[60 : 60 + len(rows)]
    return pd.Series(rows, index=idx)


def validate_symbol(symbol: str, factor: str, forward_days: int = 5) -> dict:
    ps = PriceService()
    hist = ps.get_history(symbol, period="2y")
    spy = ps.get_spy_history(period="2y")
    if hist.empty or len(hist) < 100:
        return {"symbol": symbol, "error": "insufficient history"}

    hist = hist.reset_index(drop=True)
    spy = spy.reset_index(drop=True)
    scores = _factor_series(symbol, hist, spy, factor)
    fwd = hist["close"].pct_change(forward_days).shift(-forward_days)
    aligned = pd.concat([scores, fwd], axis=1, join="inner").dropna()
    aligned.columns = ["score", "fwd_ret"]

    if len(aligned) < 40:
        return {"symbol": symbol, "error": "insufficient aligned rows"}

    ic = float(aligned["score"].corr(aligned["fwd_ret"]))
    aligned["quintile"] = pd.qcut(aligned["score"], 5, labels=False, duplicates="drop")
    q_means = aligned.groupby("quintile")["fwd_ret"].mean()
    spread = float(q_means.iloc[-1] - q_means.iloc[0]) if len(q_means) >= 2 else 0.0

    return {
        "symbol": symbol,
        "factor": factor,
        "ic": round(ic, 4),
        "quintile_spread": round(spread * 100, 3),
        "observations": len(aligned),
        "verdict": "predictive" if ic > 0.05 and spread > 0 else "weak",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Factor validation for scan signals")
    parser.add_argument("--symbols", help="Comma-separated tickers (optional with --panel)")
    parser.add_argument("--factor", default="momentum_20d")
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument(
        "--panel",
        action="store_true",
        help="Run full sleeve IC panel and persist to factor_ic_history",
    )
    parser.add_argument("--rebalance", action="store_true", help="Rebalance factor weights after panel")
    args = parser.parse_args()

    if args.panel:
        from engines.weighting.ic_panel import run_ic_panel
        from engines.weighting.weight_store import WeightStore

        summary = run_ic_panel(forward_days=args.forward_days)
        print(json.dumps(summary, indent=2))
        if args.rebalance:
            reb = WeightStore.rebalance_all_sleeves(smooth=True)
            print(json.dumps({"rebalance": {k: list(v.keys()) for k, v in reb.items()}}, indent=2))
        return

    if not args.symbols:
        parser.error("--symbols required unless --panel is set")

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    results = [validate_symbol(s, args.factor, args.forward_days) for s in symbols]
    summary = {
        "factor": args.factor,
        "forward_days": args.forward_days,
        "results": results,
        "avg_ic": round(
            float(np.mean([r["ic"] for r in results if "ic" in r])),
            4,
        )
        if any("ic" in r for r in results)
        else None,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
