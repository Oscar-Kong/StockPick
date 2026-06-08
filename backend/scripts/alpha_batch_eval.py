#!/usr/bin/env python3
"""Batch-evaluate OpenAlpha-inspired formulas on a US symbol universe.

Usage:
  cd backend
  .venv/bin/python scripts/alpha_batch_eval.py --symbols AAPL,MSFT,NVDA
  .venv/bin/python scripts/alpha_batch_eval.py --universe watchlist
  .venv/bin/python scripts/alpha_batch_eval.py --list
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

RESEARCH_DIR = BACKEND / "data_store" / "research"


def _universe_symbols(mode: str) -> list[str]:
    if mode == "watchlist":
        from data.cache import get_watchlist

        return [i["symbol"] for i in get_watchlist()]
    if mode == "sp500":
        from engines.weighting.ic_panel import _panel_symbols

        return _panel_symbols()
    return []


def _ic_for_symbol(symbol: str, factor_key: str, forward_days: int) -> dict:
    from data.price_service import PriceService
    from engines.factor.expr import load_registry
    from scoring.openalpha_factors import score_openalpha_factor

    formula = next((f for f in load_registry() if f.factor_key == factor_key), None)
    ps = PriceService()
    hist = ps.get_history(symbol, period="2y")
    spy = ps.get_spy_history(period="2y")
    if hist.empty or len(hist) < 100:
        return {"symbol": symbol, "error": "insufficient history"}

    hist = hist.reset_index(drop=True)
    spy = spy.reset_index(drop=True)
    scores: list[float] = []
    for i in range(60, len(hist) - forward_days):
        window = hist.iloc[: i + 1]
        spy_w = spy.iloc[: min(i + 1, len(spy))]
        sc = score_openalpha_factor(factor_key, window, spy_w)
        if sc is None:
            continue
        scores.append(sc)
    if len(scores) < 30:
        return {"symbol": symbol, "error": "insufficient scores"}

    idx = hist.index[60 : 60 + len(scores)]
    score_s = pd.Series(scores, index=idx)
    fwd = hist["close"].pct_change(forward_days).shift(-forward_days)
    aligned = pd.concat([score_s, fwd], axis=1, join="inner").dropna()
    aligned.columns = ["score", "fwd_ret"]
    if len(aligned) < 25:
        return {"symbol": symbol, "error": "insufficient aligned rows"}

    ic = float(aligned["score"].corr(aligned["fwd_ret"]))
    aligned["quintile"] = pd.qcut(aligned["score"], 5, labels=False, duplicates="drop")
    q_means = aligned.groupby("quintile")["fwd_ret"].mean()
    spread = float(q_means.iloc[-1] - q_means.iloc[0]) if len(q_means) >= 2 else 0.0
    return {
        "symbol": symbol,
        "factor_key": factor_key,
        "formula_id": formula.id if formula else factor_key,
        "ic": round(ic, 4),
        "quintile_spread_pct": round(spread * 100, 3),
        "observations": len(aligned),
        "verdict": "predictive" if ic > 0.03 and spread > 0 else "weak",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch OpenAlpha-inspired alpha IC eval")
    parser.add_argument("--symbols", help="Comma-separated tickers")
    parser.add_argument("--universe", choices=("watchlist", "sp500"), help="Preset universe")
    parser.add_argument("--forward-days", type=int, default=5)
    parser.add_argument("--list", action="store_true", help="List registry formulas")
    parser.add_argument("--export", action="store_true", help="Write JSON to data_store/research/")
    args = parser.parse_args()

    from engines.factor.expr import load_registry, registry_summary

    if args.list:
        print(json.dumps(registry_summary(), indent=2))
        return

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    elif args.universe:
        symbols = _universe_symbols(args.universe)
    else:
        symbols = _universe_symbols("sp500")[:10]

    if not symbols:
        raise SystemExit("No symbols — pass --symbols or --universe watchlist")

    formulas = load_registry()
    report: dict = {"symbols": symbols, "forward_days": args.forward_days, "factors": []}

    for formula in formulas:
        rows = [_ic_for_symbol(sym, formula.factor_key, args.forward_days) for sym in symbols]
        ics = [r["ic"] for r in rows if "ic" in r]
        report["factors"].append(
            {
                "id": formula.id,
                "factor_key": formula.factor_key,
                "display_name": formula.display_name,
                "openalpha_ref": formula.openalpha_ref,
                "avg_ic": round(float(np.mean(ics)), 4) if ics else None,
                "symbol_results": rows,
            }
        )

    print(json.dumps(report, indent=2))

    if args.export:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        out = RESEARCH_DIR / "openalpha_batch_eval.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
