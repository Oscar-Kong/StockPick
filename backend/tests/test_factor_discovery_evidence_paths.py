"""Tests for canonical factor-discovery evidence path resolution."""
from __future__ import annotations

from pathlib import Path

import config
from services.factor_discovery.evidence_paths import FactorDiscoveryPaths, factor_discovery_paths


def test_factor_discovery_paths_default_under_backend_data(monkeypatch, tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    monkeypatch.setattr(config, "BASE_DIR", backend)
    monkeypatch.setattr(config, "FACTOR_RESEARCH_SNAPSHOT_ROOT", "")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_STAGING_INPUT_ROOT", "")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_STAGING_AUDIT_ROOT", "")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_EXTENDED_STAGING_ROOT", "")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_ACCEPTANCE_ROOT", "")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_PROMOTION_EVIDENCE_ROOT", "")

    import services.factor_discovery.evidence_paths as mod

    monkeypatch.setattr(mod, "_default_paths", None)
    paths = factor_discovery_paths()
    base = backend / "data" / "factor_discovery"

    assert paths.backend_root == backend
    assert paths.snapshots == base / "snapshots"
    assert paths.staging_input == base / "staging_input"
    assert paths.staging_audits == base / "staging_audits"
    assert paths.extended_staging == base / "extended_staging"
    assert paths.acceptance == base / "acceptance"
    assert paths.promotion_evidence == base / "promotion_evidence"


def test_staging_audit_artifact_uses_canonical_root(tmp_path):
    from services.factor_discovery.staging.audit_artifact import FactorDiscoveryStagingAuditArtifact

    canonical = tmp_path / "staging_audits"
    store = FactorDiscoveryStagingAuditArtifact(storage_root=canonical)
    artifact = store.build(
        environment={"env": "test"},
        preflight={"ok": True},
        acceptance={"ok": True},
        actor="test",
    )
    path = store.persist(artifact)
    assert path.parent == canonical
    assert store.latest() is not None
