#!/usr/bin/env python3
"""Cross-process Factor Discovery run reproducibility verification."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.reproduce import FactorDiscoveryReproduceService


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify persisted Factor Discovery run identity chain")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--compare-run-id", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    svc = FactorDiscoveryReproduceService()
    result = svc.verify_run(args.run_id, compare_run_id=args.compare_run_id)
    payload = result.to_dict()
    payload["identity_fingerprint"] = svc.identity_fingerprint(args.run_id)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload)
    failed = (
        not result.artifact_integrity_ok
        or result.comparison_status == "MISMATCH"
        or not result.validation_artifact_hash_match
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
