#!/usr/bin/env python3
"""Run quant v2 daily jobs manually (regime + IC panel + optional rebalance)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from data.cache import init_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebalance", action="store_true", help="Force weight rebalance")
    args = parser.parse_args()
    init_db()
    from services.quant_jobs import run_daily_quant_jobs

    out = run_daily_quant_jobs(force_rebalance=args.rebalance)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
