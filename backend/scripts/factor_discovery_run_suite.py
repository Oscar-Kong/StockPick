#!/usr/bin/env python3
"""Run supervised staging Factor Discovery experiment suite."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
import yaml

from services.factor_discovery.staging.import_config import require_staging_mutations_enabled
from services.factor_discovery.staging.run_suite import FactorDiscoveryStagingRunSuite


def _load_run_config(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("config must be a mapping")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Materialize snapshot and run frozen staging factor")
    parser.add_argument("--config", help="Optional YAML run config")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--snapshot-id", default=None, help="Use existing verified snapshot")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    require_staging_mutations_enabled()
    if config.FACTOR_RESEARCH_DATA_PROVIDER != "historical_store":
        print("FACTOR_RESEARCH_DATA_PROVIDER must be historical_store", file=sys.stderr)
        return 2

    suite = FactorDiscoveryStagingRunSuite()
    start = args.start
    end = args.end
    if args.config:
        cfg = _load_run_config(Path(args.config))
        start = start or cfg.get("start_session")
        end = end or cfg.get("end_session")

    if args.snapshot_id:
        result = suite.run_supervised_experiment(snapshot_id=args.snapshot_id)
    elif start and end:
        result = suite.run_full_staging_pipeline(start_session=start, end_session=end)
    else:
        print("Provide --config with start/end or --snapshot-id", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result)
    blockers = result.get("blocking_codes") or []
    if result.get("stage") == "snapshot" and result.get("blocking_codes"):
        blockers = result["blocking_codes"]
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
