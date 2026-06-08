#!/usr/bin/env python3
"""Search linear combos of OpenAlpha-inspired factors using batch IC results.

Usage:
  cd backend
  .venv/bin/python scripts/alpha_batch_eval.py --universe sp500 --export
  .venv/bin/python scripts/alpha_combo_optimizer.py
  .venv/bin/python scripts/alpha_combo_optimizer.py --sleeve medium --top 3
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

RESEARCH_DIR = BACKEND / "data_store" / "research"
BATCH_PATH = RESEARCH_DIR / "openalpha_batch_eval.json"


def _load_or_run() -> dict:
    if BATCH_PATH.exists():
        return json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    raise SystemExit(
        f"Missing {BATCH_PATH}. Run: python scripts/alpha_batch_eval.py --universe sp500 --export"
    )


def optimize_combo(report: dict, sleeve: str | None, top_k: int) -> dict:
    from engines.factor.expr import load_registry

    registry = {f.factor_key: f for f in load_registry()}
    candidates = []
    for block in report.get("factors", []):
        fk = block["factor_key"]
        formula = registry.get(fk)
        if sleeve and formula and formula.sleeve != sleeve:
            continue
        avg_ic = block.get("avg_ic")
        if avg_ic is None:
            continue
        candidates.append(
            {
                "factor_key": fk,
                "id": block["id"],
                "display_name": block["display_name"],
                "avg_ic": avg_ic,
                "sleeve": formula.sleeve if formula else "?",
            }
        )

    candidates.sort(key=lambda x: abs(x["avg_ic"]), reverse=True)
    pool = candidates[: max(top_k, 2)]

    best: dict | None = None
    for r in range(1, min(4, len(pool) + 1)):
        for combo in itertools.combinations(pool, r):
            weights = np.array([max(0.1, abs(c["avg_ic"])) for c in combo])
            weights = weights / weights.sum()
            combo_ic = float(sum(w * c["avg_ic"] for w, c in zip(weights, combo)))
            entry = {
                "sleeve": sleeve or "mixed",
                "factors": [c["factor_key"] for c in combo],
                "display_names": [c["display_name"] for c in combo],
                "weights": [round(float(w), 4) for w in weights],
                "estimated_combo_ic": round(combo_ic, 4),
            }
            if best is None or abs(entry["estimated_combo_ic"]) > abs(best["estimated_combo_ic"]):
                best = entry

    out = {
        "source": str(BATCH_PATH),
        "candidates_ranked": candidates,
        "recommended_combo": best,
        "note": "Heuristic IC-weighted combo — revalidate on forward labels before enabling live.",
    }
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAlpha-inspired factor combo optimizer")
    parser.add_argument("--sleeve", choices=("penny", "medium", "compounder"))
    parser.add_argument("--top", type=int, default=5, help="Max factors in search pool")
    parser.add_argument("--export", action="store_true")
    args = parser.parse_args()

    report = _load_or_run()
    result = optimize_combo(report, args.sleeve, args.top)
    print(json.dumps(result, indent=2))

    if args.export:
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        out = RESEARCH_DIR / f"openalpha_combo_{args.sleeve or 'all'}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
