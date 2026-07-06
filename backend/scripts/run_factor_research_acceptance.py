#!/usr/bin/env python3
"""Phase 11 canonical factor-research acceptance workflow."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.acceptance.final_acceptance import FactorResearchAcceptanceRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase 11 factor-research acceptance")
    parser.add_argument(
        "--mode",
        choices=["fixture", "real"],
        default="fixture",
        help="fixture=deterministic CI checks; real=local DB validation",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument("--no-persist", action="store_true", help="Skip writing acceptance artifact")
    args = parser.parse_args()

    runner = FactorResearchAcceptanceRunner(mode=args.mode)
    report = runner.run()
    if not args.no_persist:
        path = runner.persist(report)
        artifact_note = str(path)
    else:
        artifact_note = "(not persisted)"

    if args.json:
        payload = report.to_dict()
        payload["artifact_path"] = artifact_note
        print(json.dumps(payload, indent=2))
    else:
        print(f"Mode: {report.mode}")
        print(f"Status: {report.status}")
        print(f"Blockers: {report.blockers or 'none'}")
        print(f"Warnings: {report.warnings or 'none'}")
        print(f"Total: {report.performance.get('total_ms')}ms")
        print(f"Artifact: {artifact_note}")
        for check in report.checks:
            mark = {"pass": "✓", "fail": "✗", "warn": "!", "skip": "-"}.get(check.status, "?")
            print(f"  [{mark}] {check.check_id}: {check.message} ({check.duration_ms}ms)")

    return 0 if report.status == "PHASE_11_COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
