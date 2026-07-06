"""Factor Discovery data provider abstraction."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from engines.factor.discovery.panel_models import FactorInputPanel, validate_input_panel
from engines.factor.discovery.provenance import PanelFieldProvenance
from engines.factor.discovery.session_hashing import canonical_session_hash
from engines.factor.discovery.sessions import extract_canonical_sessions
from services.factor_discovery.errors import FactorDiscoveryError
from services.factor_discovery.evidence_paths import factor_discovery_paths

FIXTURE_PROVIDER_ID = "fixture_provider_v1"
DISABLED_PROVIDER_ID = "disabled_provider_v1"


@dataclass(frozen=True)
class FactorResearchSnapshotRef:
    snapshot_id: str
    provider_id: str
    data_source_policy_id: str
    panel_hash: str
    canonical_session_hash: str
    universe_source: str
    universe_version: str
    universe_pit_evidence: dict
    field_list: list[str]
    field_provenance_summary: dict
    adjustment_status: str
    start_session: str
    end_session: str
    row_count: int
    symbol_count: int
    date_count: int
    storage_reference: str | None
    storage_format: str
    artifact_present: bool


class FactorResearchDataProvider(Protocol):
    provider_id: str

    def load_snapshot(
        self,
        *,
        snapshot_id: str | None = None,
        start_session: str | None = None,
        end_session: str | None = None,
        universe_source: str | None = None,
    ) -> tuple[FactorInputPanel, FactorResearchSnapshotRef]:
        ...


class DisabledFactorResearchDataProvider:
    provider_id = DISABLED_PROVIDER_ID

    def load_snapshot(self, **kwargs) -> tuple[FactorInputPanel, FactorResearchSnapshotRef]:
        raise FactorDiscoveryError(
            "FACTOR_RESEARCH_DATA_PROVIDER_NOT_CONFIGURED",
            "No safe historical Factor Discovery data provider is configured",
        )


class FixtureFactorResearchDataProvider:
    """Test-only deterministic provider."""

    provider_id = FIXTURE_PROVIDER_ID

    def __init__(self, *, panel_builder, empty_universe: bool = False, reject_static_sector: bool = False) -> None:
        self._panel_builder = panel_builder
        self._empty_universe = empty_universe
        self._reject_static_sector = reject_static_sector

    def load_snapshot(self, **kwargs) -> tuple[FactorInputPanel, FactorResearchSnapshotRef]:
        panel = self._panel_builder()
        if self._empty_universe:
            panel = FactorInputPanel(
                frame=panel.frame,
                eligibility=panel.eligibility & False,
                data_source_policy_id=panel.data_source_policy_id,
                provider_id=panel.provider_id,
                prices_adjusted=panel.prices_adjusted,
                field_provenance=panel.field_provenance,
                has_universe_membership=False,
            )
        if self._reject_static_sector:
            prov = dict(panel.field_provenance)
            sector = prov.get("sector")
            if sector is not None:
                prov["sector"] = PanelFieldProvenance(
                    field_id=sector.field_id,
                    source_type=sector.source_type,
                    pit_state=sector.pit_state,
                    provider_id=sector.provider_id,
                    source_policy_id=sector.source_policy_id,
                    is_adjusted=sector.is_adjusted,
                    notes="static_current_classification",
                )
            panel = FactorInputPanel(
                frame=panel.frame,
                eligibility=panel.eligibility,
                data_source_policy_id=panel.data_source_policy_id,
                provider_id=panel.provider_id,
                prices_adjusted=panel.prices_adjusted,
                field_provenance=prov,
            )
        if self._empty_universe:
            raise FactorDiscoveryError("EMPTY_PIT_UNIVERSE", "PIT universe evidence is empty or missing")
        validate_input_panel(panel)
        calendar = extract_canonical_sessions(panel.frame)
        session_hash = canonical_session_hash(calendar)
        snapshot_id = kwargs.get("snapshot_id") or f"fdsnap_fixture_{session_hash[-12:]}"
        prov_summary = {
            k: v.model_dump(mode="json") if hasattr(v, "model_dump") else v
            for k, v in sorted(panel.field_provenance.items())
        }
        ref = FactorResearchSnapshotRef(
            snapshot_id=snapshot_id,
            provider_id=self.provider_id,
            data_source_policy_id=panel.data_source_policy_id,
            panel_hash=panel.content_hash,
            canonical_session_hash=session_hash,
            universe_source=kwargs.get("universe_source") or "fixture_universe_v1",
            universe_version="fixture_v1",
            universe_pit_evidence={"verified": True, "source": "fixture"},
            field_list=sorted(panel.frame.columns.tolist()),
            field_provenance_summary=prov_summary,
            adjustment_status="adjusted" if panel.prices_adjusted else "raw",
            start_session=str(panel.start_date),
            end_session=str(panel.end_date),
            row_count=panel.row_count,
            symbol_count=panel.symbol_count,
            date_count=panel.date_count,
            storage_reference=None,
            storage_format="in_memory_fixture",
            artifact_present=True,
        )
        return panel, ref


def get_runtime_factor_research_provider(*, fixture_builder=None):
    from config import APP_ENV, FACTOR_RESEARCH_DATA_PROVIDER

    if fixture_builder is not None:
        return FixtureFactorResearchDataProvider(panel_builder=fixture_builder)
    provider = FACTOR_RESEARCH_DATA_PROVIDER
    if provider == "fixture":
        if APP_ENV not in ("test", "development"):
            raise FactorDiscoveryError("FIXTURE_PROVIDER_FORBIDDEN", "fixture provider not allowed in production")
        raise FactorDiscoveryError("FIXTURE_BUILDER_REQUIRED", "fixture provider requires explicit fixture_builder")
    if provider == "historical_store":
        from services.factor_discovery.staging.provider_gate import require_historical_store_for_staging

        require_historical_store_for_staging()
        from services.factor_discovery.historical_store_provider import HistoricalStoreFactorResearchDataProvider

        return HistoricalStoreFactorResearchDataProvider()
    return DisabledFactorResearchDataProvider()


def persist_panel_snapshot_artifact(snapshot_id: str, panel: FactorInputPanel, *, base_dir: Path | None = None) -> str:
    root = base_dir or factor_discovery_paths().snapshots
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{snapshot_id}.json"
    payload = {
        "snapshot_id": snapshot_id,
        "panel_hash": panel.content_hash,
        "columns": sorted(panel.frame.columns.tolist()),
        "index": [
            [pd.Timestamp(d).strftime("%Y-%m-%d"), sym]
            for d, sym in panel.frame.index
        ],
        "values": json.loads(panel.frame.reset_index(drop=True).to_json(orient="values")),
        "eligibility": {f"{pd.Timestamp(d).date()}|{sym}": bool(v) for (d, sym), v in panel.eligibility.items()},
    }
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return str(path)
