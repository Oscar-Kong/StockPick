"""Persistence for extended staging run artifacts."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from services.factor_discovery.evidence_paths import factor_discovery_paths


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


EXTENDED_STAGING_ARTIFACT_SCHEMA = "factor_extended_staging_report_v1"


class ExtendedStagingArtifactStore:
    def __init__(self, *, output_root: Path | None = None) -> None:
        self._root = output_root or factor_discovery_paths().extended_staging
        self._root.mkdir(parents=True, exist_ok=True)

    def persist(self, report: dict) -> Path:
        run_id = report.get("staging_run_id") or report.get("manifest", {}).get("staging_run_id") or "unknown"
        path = self._root / f"extended_staging_{run_id}.json"
        body = {
            "artifact_schema_version": EXTENDED_STAGING_ARTIFACT_SCHEMA,
            "created_at": _utcnow(),
            **report,
        }
        path.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
        (self._root / "latest.json").write_text(json.dumps({"path": str(path), "staging_run_id": run_id}, indent=2), encoding="utf-8")
        return path

    def latest(self) -> dict | None:
        pointer = self._root / "latest.json"
        if not pointer.exists():
            files = sorted(self._root.glob("extended_staging_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not files:
                return None
            return json.loads(files[0].read_text(encoding="utf-8"))
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        path = Path(meta["path"])
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
