"""Canonical filesystem paths for factor-discovery evidence artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import config


def _resolve_path(env_value: str, default: Path) -> Path:
    return Path(env_value) if env_value else default


@dataclass(frozen=True)
class FactorDiscoveryPaths:
    backend_root: Path
    snapshots: Path
    staging_input: Path
    staging_audits: Path
    extended_staging: Path
    acceptance: Path
    promotion_evidence: Path

    @classmethod
    def from_config(cls) -> FactorDiscoveryPaths:
        backend = config.BASE_DIR
        base = backend / "data" / "factor_discovery"
        return cls(
            backend_root=backend,
            snapshots=_resolve_path(config.FACTOR_RESEARCH_SNAPSHOT_ROOT, base / "snapshots"),
            staging_input=_resolve_path(config.FACTOR_RESEARCH_STAGING_INPUT_ROOT, base / "staging_input"),
            staging_audits=_resolve_path(config.FACTOR_RESEARCH_STAGING_AUDIT_ROOT, base / "staging_audits"),
            extended_staging=_resolve_path(config.FACTOR_RESEARCH_EXTENDED_STAGING_ROOT, base / "extended_staging"),
            acceptance=_resolve_path(config.FACTOR_RESEARCH_ACCEPTANCE_ROOT, base / "acceptance"),
            promotion_evidence=_resolve_path(
                config.FACTOR_RESEARCH_PROMOTION_EVIDENCE_ROOT,
                base / "promotion_evidence",
            ),
        )


_default_paths: FactorDiscoveryPaths | None = None


def factor_discovery_paths() -> FactorDiscoveryPaths:
    global _default_paths
    if _default_paths is None:
        _default_paths = FactorDiscoveryPaths.from_config()
    return _default_paths
