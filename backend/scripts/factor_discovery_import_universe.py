#!/usr/bin/env python3
"""Import versioned PIT universe membership for Factor Discovery staging."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.import_config import load_universe_import_config
from services.factor_discovery.staging.import_universe import FactorDiscoveryStagingUniverseImporter


def main() -> int:
    parser = argparse.ArgumentParser(description="Import staging universe_pit membership from versioned config")
    parser.add_argument("--config", required=True, help="Path to universe import YAML config")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without committing")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    cfg = load_universe_import_config(Path(args.config))
    report = FactorDiscoveryStagingUniverseImporter().import_from_config(cfg, dry_run=args.dry_run)
    payload = report.to_dict()
    payload["config"] = cfg.to_dict()
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(payload)
    return 1 if report.blocking_codes or report.status == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
