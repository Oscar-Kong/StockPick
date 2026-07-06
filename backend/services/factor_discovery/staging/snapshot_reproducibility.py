"""Snapshot reproducibility verification."""
from __future__ import annotations

from dataclasses import dataclass

from services.factor_discovery.data_provider import FactorResearchDataProvider
from services.factor_discovery.snapshot_service import FactorResearchSnapshotService, SnapshotRequest, snapshot_request_hash


@dataclass
class SnapshotReproducibilityResult:
    snapshot_id_a: str
    snapshot_id_b: str
    identity_hash: str
    panel_hash_match: bool
    session_hash_match: bool
    row_count_match: bool
    symbol_count_match: bool
    date_count_match: bool
    reload_verified: bool
    status: str

    def to_dict(self) -> dict:
        return {
            "snapshot_id_a": self.snapshot_id_a,
            "snapshot_id_b": self.snapshot_id_b,
            "identity_hash": self.identity_hash,
            "panel_hash_match": self.panel_hash_match,
            "session_hash_match": self.session_hash_match,
            "row_count_match": self.row_count_match,
            "symbol_count_match": self.symbol_count_match,
            "date_count_match": self.date_count_match,
            "reload_verified": self.reload_verified,
            "status": self.status,
        }


class FactorDiscoverySnapshotReproducibilityService:
    def __init__(self, *, storage_root=None) -> None:
        self._svc = FactorResearchSnapshotService(storage_root=storage_root)

    def verify_identical_request(
        self,
        provider: FactorResearchDataProvider,
        req: SnapshotRequest,
    ) -> SnapshotReproducibilityResult:
        identity = snapshot_request_hash(req)
        id_a, _, ref_a = self._svc.materialize(provider, req)
        id_b, _, ref_b = self._svc.materialize(provider, req)
        reload_panel = self._svc.load_verified(id_a)
        row = self._svc._repo.get(id_a)
        reload_ok = reload_panel.row_count == row.row_count
        status = "EXACT_MATCH" if id_a == id_b and ref_a.panel_hash == ref_b.panel_hash and reload_ok else "MISMATCH"
        return SnapshotReproducibilityResult(
            snapshot_id_a=id_a,
            snapshot_id_b=id_b,
            identity_hash=identity,
            panel_hash_match=ref_a.panel_hash == ref_b.panel_hash,
            session_hash_match=ref_a.canonical_session_hash == ref_b.canonical_session_hash,
            row_count_match=ref_a.row_count == ref_b.row_count,
            symbol_count_match=ref_a.symbol_count == ref_b.symbol_count,
            date_count_match=ref_a.date_count == ref_b.date_count,
            reload_verified=reload_ok,
            status=status,
        )

    def verify_identity_changes_on_version_change(
        self,
        base: SnapshotRequest,
        *,
        changed_provider_version: str,
    ) -> dict:
        h1 = snapshot_request_hash(base)
        changed = SnapshotRequest(
            provider_id=base.provider_id,
            data_source_policy_id=base.data_source_policy_id,
            start_session=base.start_session,
            end_session=base.end_session,
            universe_source=base.universe_source,
            required_fields=base.required_fields,
            provider_data_version=changed_provider_version,
        )
        h2 = snapshot_request_hash(changed)
        return {"passed": h1 != h2, "base_hash": h1, "changed_hash": h2}
