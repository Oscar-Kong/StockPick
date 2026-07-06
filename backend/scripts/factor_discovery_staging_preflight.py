#!/usr/bin/env python3
"""Factor Discovery staging preflight CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Factor Discovery staging preflight (read-only)")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    parser.add_argument("--allow-test", action="store_true", help="Allow test environment without staging flag")
    args = parser.parse_args()
    report = FactorDiscoveryStagingPreflightService().run(allow_test=args.allow_test)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Blocking reasons: {report['blocking_reasons']}")
    return 1 if report["blocking_reasons"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
