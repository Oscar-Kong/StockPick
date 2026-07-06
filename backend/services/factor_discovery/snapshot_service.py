"""Immutable Factor Discovery research snapshot materialization."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel, validate_input_panel
from engines.factor.discovery.provenance import PanelFieldProvenance
from engines.factor.discovery.result_hashing import hash_panel_content
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import extract_canonical_sessions
from services.factor_discovery.artifact_integrity import ArtifactIntegrityError
from services.factor_discovery.data_provider import FactorResearchDataProvider, FactorResearchSnapshotRef
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.evidence_paths import factor_discovery_paths
from services.factor_discovery.repositories import FactorDataSnapshotRepository

_SNAPSHOT_ID_RE = re.compile(r"^[a-zA-Z0-9_:-]{8,128}$")
_STORAGE_FORMAT = "factor_snapshot_csv_bundle_v1"


@dataclass(frozen=True)
class SnapshotRequest:
    provider_id: str
    data_source_policy_id: str
    start_session: str | None
    end_session: str | None
    universe_source: str
    required_fields: frozenset[str]
    provider_data_version: str


def snapshot_request_hash(req: SnapshotRequest) -> str:
    payload = {
        "provider_id": req.provider_id,
        "policy": req.data_source_policy_id,
        "start": req.start_session,
        "end": req.end_session,
        "universe": req.universe_source,
        "fields": sorted(req.required_fields),
        "provider_data_version": req.provider_data_version,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}"


def _safe_snapshot_path(root: Path, snapshot_id: str) -> Path:
    if not _SNAPSHOT_ID_RE.match(snapshot_id):
        raise FactorDiscoveryError("INVALID_SNAPSHOT_ID", snapshot_id)
    root = root.resolve()
    path = (root / f"{snapshot_id}.snapshot.json").resolve()
    if not str(path).startswith(str(root)):
        raise FactorDiscoveryError("SNAPSHOT_PATH_ESCAPE", "invalid snapshot path")
    return path


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _panel_to_csv(panel: FactorInputPanel) -> str:
    export = panel.frame.reset_index()
    export["eligible"] = panel.eligibility.reindex(panel.frame.index).astype(int).values
    buf = io.StringIO()
    export.to_csv(buf, index=False, float_format="%.15g")
    return buf.getvalue()


def _panel_from_csv(csv_text: str) -> tuple[pd.DataFrame, pd.Series]:
    df = pd.read_csv(io.StringIO(csv_text))
    if "eligible" not in df.columns:
        raise FactorDiscoveryError("SNAPSHOT_FORMAT_INVALID", "missing eligible column")
    eligibility = df.pop("eligible").astype(bool)
    df["date"] = pd.to_datetime(df["date"])
    frame = df.set_index(["date", "symbol"]).sort_index()
    eligibility.index = frame.index
    return frame, eligibility


class FactorResearchSnapshotService:
    def __init__(self, *, storage_root: Path | None = None) -> None:
        self._root = storage_root or factor_discovery_paths().snapshots
        self._repo = FactorDataSnapshotRepository()

    def materialize(
        self,
        provider: FactorResearchDataProvider,
        req: SnapshotRequest,
        *,
        plan=None,
    ) -> tuple[str, FactorInputPanel, FactorResearchSnapshotRef]:
        identity = snapshot_request_hash(req)
        existing = self._repo.get_by_identity(identity)
        if existing and existing.artifact_present and existing.storage_reference:
            panel = self.load_verified(existing.snapshot_id)
            ref = self._ref_from_row(existing)
            return existing.snapshot_id, panel, ref

        snapshot_id = f"fdsnap_{identity.split(':')[-1][:12]}"
        panel, ref = provider.load_snapshot(
            snapshot_id=snapshot_id,
            start_session=req.start_session,
            end_session=req.end_session,
            required_fields=set(req.required_fields),
        )
        validate_input_panel(panel, plan=plan)
        calendar = extract_canonical_sessions(panel.frame)
        session_hash = canonical_session_hash(calendar)
        panel_hash = hash_panel_content(
            panel.frame,
            eligibility=panel.eligibility,
            data_source_policy_id=panel.data_source_policy_id,
            provider_id=panel.provider_id,
            prices_adjusted=panel.prices_adjusted,
            field_provenance=panel.field_provenance,
            panel_version=panel.panel_version,
            canonical_session_hash_value=session_hash,
        )
        prov_summary = {
            k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            for k, v in sorted(panel.field_provenance.items())
        }
        path = _safe_snapshot_path(self._root, snapshot_id)
        payload = {
            "snapshot_id": snapshot_id,
            "identity_hash": identity,
            "panel_hash": panel_hash,
            "canonical_session_hash": session_hash,
            "schema_version": "factor-snapshot-v1",
            "storage_format": _STORAGE_FORMAT,
            "panel_csv": _panel_to_csv(panel),
            "field_provenance_summary": prov_summary,
        }
        _atomic_write_text(path, json.dumps(payload, sort_keys=True))
        ref = FactorResearchSnapshotRef(
            snapshot_id=snapshot_id,
            provider_id=ref.provider_id,
            data_source_policy_id=ref.data_source_policy_id,
            panel_hash=panel_hash,
            canonical_session_hash=session_hash,
            universe_source=ref.universe_source,
            universe_version=req.provider_data_version,
            universe_pit_evidence=ref.universe_pit_evidence,
            field_list=sorted(panel.frame.columns.tolist()),
            field_provenance_summary=prov_summary,
            adjustment_status=ref.adjustment_status,
            start_session=ref.start_session,
            end_session=ref.end_session,
            row_count=panel.row_count,
            symbol_count=panel.symbol_count,
            date_count=panel.date_count,
            storage_reference=str(path),
            storage_format=_STORAGE_FORMAT,
            artifact_present=True,
        )
        self._repo.upsert(ref, storage_reference=str(path))
        self._repo.set_identity(snapshot_id, identity, provider_data_version=req.provider_data_version)
        return snapshot_id, panel, ref

    def load_verified(self, snapshot_id: str) -> FactorInputPanel:
        row = self._repo.get(snapshot_id)
        if row is None or not row.storage_reference or not row.artifact_present:
            raise FactorDiscoveryError("SNAPSHOT_NOT_FOUND", snapshot_id)
        path = Path(row.storage_reference)
        if not path.exists():
            raise FactorDiscoveryError("SNAPSHOT_ARTIFACT_MISSING", snapshot_id)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("storage_format") not in {_STORAGE_FORMAT, "factor_snapshot_json_v1"}:
            raise FactorDiscoveryError("SNAPSHOT_FORMAT_INVALID", payload.get("storage_format", "unknown"))

        if payload.get("storage_format") == _STORAGE_FORMAT:
            frame, eligibility = _panel_from_csv(payload["panel_csv"])
            prov_summary = payload.get("field_provenance_summary") or json.loads(row.field_provenance_summary_json or "{}")
        else:
            df = pd.DataFrame(payload["data"])
            frame = df.set_index(["date", "symbol"]).sort_index()
            frame.index = frame.index.set_levels(pd.to_datetime(frame.index.levels[0]), level=0)
            elig_map = payload.get("eligibility", {})
            eligibility = pd.Series({tuple(k.split("|")): v for k, v in elig_map.items()}, dtype=bool)
            eligibility.index = pd.MultiIndex.from_tuples(
                [(pd.Timestamp(d), s) for d, s in eligibility.index],
                names=["date", "symbol"],
            )
            eligibility = eligibility.reindex(frame.index, fill_value=False)
            prov_summary = json.loads(row.field_provenance_summary_json or "{}")

        provenance = {k: PanelFieldProvenance.model_validate(v) for k, v in prov_summary.items()}
        panel = FactorInputPanel(
            frame=frame,
            eligibility=eligibility,
            data_source_policy_id=row.data_source_policy_id,
            provider_id=row.provider_id,
            prices_adjusted=row.adjustment_status == "adjusted",
            field_provenance=provenance,
        )
        calendar = extract_canonical_sessions(panel.frame)
        session_hash = canonical_session_hash(calendar)
        recomputed = hash_panel_content(
            panel.frame,
            eligibility=panel.eligibility,
            data_source_policy_id=panel.data_source_policy_id,
            provider_id=panel.provider_id,
            prices_adjusted=panel.prices_adjusted,
            field_provenance=panel.field_provenance,
            panel_version=panel.panel_version,
            canonical_session_hash_value=session_hash,
        )
        if recomputed != row.panel_hash:
            raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "snapshot panel hash mismatch")
        if session_hash != row.canonical_session_hash:
            raise ArtifactIntegrityError("ARTIFACT_INTEGRITY_FAILURE", "snapshot session hash mismatch")
        return panel

    @staticmethod
    def _ref_from_row(row) -> FactorResearchSnapshotRef:
        return FactorResearchSnapshotRef(
            snapshot_id=row.snapshot_id,
            provider_id=row.provider_id,
            data_source_policy_id=row.data_source_policy_id,
            panel_hash=row.panel_hash,
            canonical_session_hash=row.canonical_session_hash,
            universe_source=row.universe_source,
            universe_version=row.universe_version,
            universe_pit_evidence=json.loads(row.universe_pit_evidence_json or "{}"),
            field_list=json.loads(row.field_list_json or "[]"),
            field_provenance_summary=json.loads(row.field_provenance_summary_json or "{}"),
            adjustment_status=row.adjustment_status,
            start_session=row.start_session,
            end_session=row.end_session,
            row_count=row.row_count,
            symbol_count=row.symbol_count,
            date_count=row.date_count,
            storage_reference=row.storage_reference,
            storage_format=row.storage_format,
            artifact_present=row.artifact_present,
        )
