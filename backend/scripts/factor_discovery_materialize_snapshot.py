#!/usr/bin/env python3
"""Materialize a staging Factor Discovery snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config

from services.factor_discovery.staging.run_suite import FactorDiscoveryStagingRunSuite


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize staging snapshot via historical_store provider")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
        print("FACTOR_RESEARCH_DATA_PROVIDER must be historical_store", file=sys.stderr)
        return 2
    result = FactorDiscoveryStagingRunSuite().materialize_snapshot(start_session=args.start, end_session=args.end)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result)
    return 1 if result.get("blocking_codes") else 0


if __name__ == "__main__":
    raise SystemExit(main())
