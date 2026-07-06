"""Immutable staging audit artifact persistence."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from services.factor_discovery.evidence_paths import factor_discovery_paths
from services.factor_discovery.staging.policies import STAGING_AUDIT_ARTIFACT_SCHEMA


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


class FactorDiscoveryStagingAuditArtifact:
    def __init__(self, *, storage_root: Path | None = None) -> None:
        self._root = storage_root or factor_discovery_paths().staging_audits
        self._root.mkdir(parents=True, exist_ok=True)

    def build(
        self,
        *,
        environment: dict,
        preflight: dict,
        acceptance: dict,
        actor: str,
        extra: dict | None = None,
    ) -> dict:
        body = {
            "artifact_schema_version": STAGING_AUDIT_ARTIFACT_SCHEMA,
            "audit_policy_version": "2026-03-01",
            "environment_identity": environment,
            "preflight": preflight,
            "acceptance": acceptance,
            "created_at": _utcnow(),
            "actor": actor,
        }
        if extra:
            body.update(extra)
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        body["artifact_hash"] = f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"
        return body

    def persist(self, artifact: dict) -> Path:
        artifact_id = artifact["artifact_hash"].split(":")[-1][:16]
        path = self._root / f"staging_audit_{artifact_id}.json"
        path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def latest(self) -> dict | None:
        files = sorted(self._root.glob("staging_audit_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))
