#!/usr/bin/env python3
"""Run walk-forward research pipeline from the CLI (no live weight updates)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from data.cache import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward research pipeline")
    parser.add_argument("--sleeve", required=True, help="penny | compounder")
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--rebalance-frequency",
        default="monthly",
        help="weekly | monthly | quarterly | N (session step)",
    )
    parser.add_argument(
        "--forward-horizons",
        default="20",
        help="Comma-separated session horizons, e.g. 5,20,60",
    )
    parser.add_argument("--max-symbols", type=int, default=30)
    parser.add_argument(
        "--no-persist-snapshots",
        action="store_true",
        help="Skip prediction snapshot writes",
    )
    args = parser.parse_args()

    horizons = [int(x.strip()) for x in args.forward_horizons.split(",") if x.strip()]
    if not horizons:
        raise SystemExit("forward-horizons must contain at least one integer")

    init_db()
    try:
        from engines.quant_db import init_quant_db

        init_quant_db()
    except Exception:
        pass

    from services.walk_forward_research_service import WalkForwardConfig, run_walk_forward_research

    cfg = WalkForwardConfig(
        sleeve=args.sleeve,
        start_date=args.start_date,
        end_date=args.end_date,
        rebalance_frequency=args.rebalance_frequency,
        forward_horizons=horizons,
        max_symbols=args.max_symbols,
        persist_snapshots=not args.no_persist_snapshots,
    )
    summary = run_walk_forward_research(cfg)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
