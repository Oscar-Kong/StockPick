#!/usr/bin/env python3
"""Factor Discovery staging audit CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.factor_discovery.staging.acceptance_gate import FactorDiscoveryStagingAcceptanceGate
from services.factor_discovery.staging.audit_artifact import FactorDiscoveryStagingAuditArtifact
from services.factor_discovery.staging.corporate_actions_audit import FactorDiscoveryCorporateActionsAuditService
from services.factor_discovery.staging.environment import resolve_staging_contract
from services.factor_discovery.staging.preflight_service import FactorDiscoveryStagingPreflightService
from services.factor_discovery.staging.survivorship_audit import FactorDiscoverySurvivorshipAuditService


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full Factor Discovery staging audit")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--actor", default="staging-cli")
    parser.add_argument("--allow-test", action="store_true")
    args = parser.parse_args()
    preflight = FactorDiscoveryStagingPreflightService().run(allow_test=args.allow_test)
    acceptance = FactorDiscoveryStagingAcceptanceGate().evaluate(preflight=preflight)
    artifact_svc = FactorDiscoveryStagingAuditArtifact()
    artifact = artifact_svc.build(
        environment=resolve_staging_contract().to_dict(),
        preflight=preflight,
        acceptance=acceptance,
        actor=args.actor,
        extra={
            "survivorship_audit": FactorDiscoverySurvivorshipAuditService().audit(),
            "corporate_actions_audit": FactorDiscoveryCorporateActionsAuditService().audit().to_dict(),
        },
    )
    path = artifact_svc.persist(artifact)
    if args.json:
        print(json.dumps(artifact, indent=2))
    else:
        print(f"Status: {acceptance['status']} — saved {path}")
    return 0 if acceptance["status"] != "NOT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
