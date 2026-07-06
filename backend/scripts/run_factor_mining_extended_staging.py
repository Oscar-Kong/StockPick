#!/usr/bin/env python3
"""Run extended Factor Discovery staging matrix (Phase 9B.2)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.sleeve import ACTIVE_SLEEVES
from services.factor_discovery.staging.extended_staging_runner import FactorMiningExtendedStagingRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Extended real-data factor mining staging validation")
    parser.add_argument(
        "--sleeves",
        default="penny,compounder",
        help=f"Comma-separated sleeves ({','.join(sorted(ACTIVE_SLEEVES))})",
    )
    parser.add_argument("--start-date", default=None, help="Optional start date (resolved against DB if omitted)")
    parser.add_argument("--end-date", default=None, help="Optional end date (resolved against DB if omitted)")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Artifact output directory (default: backend/data/factor_discovery/extended_staging)",
    )
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--dry-run", action="store_true", help="Build matrix/manifest only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sleeves = [s.strip() for s in args.sleeves.split(",") if s.strip()]
    output_dir = Path(args.output_dir) if args.output_dir else None
    runner = FactorMiningExtendedStagingRunner(output_dir=output_dir)
    result = runner.run(
        sleeves=sleeves,
        start_date=args.start_date,
        end_date=args.end_date,
        random_seed=args.random_seed,
        dry_run=args.dry_run,
    )
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        status = result.get("promotion_readiness", {}).get("status", "UNKNOWN")
        print(f"staging_run_id={result.get('staging_run_id')} status={status}")
    blockers = result.get("promotion_readiness", {}).get("blocking_findings") or result.get("blocking_reasons") or []
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
