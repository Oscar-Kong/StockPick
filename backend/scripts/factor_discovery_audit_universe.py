#!/usr/bin/env python3
"""Universe PIT audit CLI for Factor Discovery staging."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.survivorship_audit import FactorDiscoverySurvivorshipAuditService
from services.factor_discovery.staging.universe_audit import FactorDiscoveryUniverseAuditService


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit universe_pit membership for staging readiness")
    parser.add_argument("--universe-id", default=None, help="Universe identifier (informational)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    universe = FactorDiscoveryUniverseAuditService().audit()
    survivorship = FactorDiscoverySurvivorshipAuditService().audit()
    report = {
        "universe_id": args.universe_id,
        "universe_audit": universe.to_dict(),
        "survivorship_audit": survivorship,
        "blocking_reasons": list(dict.fromkeys(universe.blocking_codes + survivorship.get("blocking_codes", []))),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report)
    return 1 if report["blocking_reasons"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
