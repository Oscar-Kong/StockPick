"""Phase 9B.2 extended staging tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from core.sleeve import normalize_sleeve
from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore
from services.factor_discovery.staging.negative_controls import ExtendedStagingNegativeControls
from services.factor_discovery.staging.promotion_readiness_gate import FactorDiscoveryPromotionReadinessGate
from services.factor_discovery.staging.staging_manifest import build_extended_staging_manifest
from services.factor_discovery.staging.staging_matrix import build_staging_matrix
from services.factor_discovery.staging.supported_dates import RegimeSlice, resolve_supported_date_range
from tests.fixtures.factor_discovery.staging.helpers import seed_staging_fixture


def test_build_staging_matrix_both_sleeves():
    slices = [
        RegimeSlice("s1", "Early", "2020-01-02", "2020-03-01", "early"),
        RegimeSlice("s2", "Recent", "2020-03-02", "2020-06-01", "recent"),
    ]
    matrix = build_staging_matrix(sleeves=["penny", "compounder"], slices=slices)
    assert matrix.sleeves == ["penny", "compounder"]
    assert len(matrix.cells) == 2 * 2 * 5
    sleeves_in_cells = {c.sleeve for c in matrix.cells}
    assert sleeves_in_cells == {"penny", "compounder"}


def test_manifest_hash_stable():
    m1 = build_extended_staging_manifest(
        staging_run_id="ext_test",
        sleeves=["penny"],
        start_date="2020-01-02",
        end_date="2020-06-01",
        pit_universe_version="v1",
        matrix_spec={"cell_count": 1},
    )
    m2 = build_extended_staging_manifest(
        staging_run_id="ext_test",
        sleeves=["penny"],
        start_date="2020-01-02",
        end_date="2020-06-01",
        pit_universe_version="v1",
        matrix_spec={"cell_count": 1},
    )
    assert m1.to_dict()["manifest_hash"] == m2.to_dict()["manifest_hash"]


def test_supported_dates_from_fixture(isolated_backend_env):
    seed_staging_fixture(variant="long_history")
    dr = resolve_supported_date_range()
    assert dr.supported_start is not None
    assert dr.overlap_sessions >= 60
    assert dr.slices


def test_promotion_gate_requires_both_sleeves():
    gate = FactorDiscoveryPromotionReadinessGate().evaluate(
        preflight_blockers=[],
        sleeves_tested=["penny"],
        negative_controls=[],
        reproducibility_results=[],
        cell_results=[],
    )
    assert gate["status"] == "NOT_READY_FOR_PROMOTION_REVIEW"
    assert "both_active_sleeves_not_tested" in gate["blocking_findings"]


def test_promotion_gate_ready_when_clean():
    gate = FactorDiscoveryPromotionReadinessGate().evaluate(
        preflight_blockers=[],
        sleeves_tested=["penny", "compounder"],
        negative_controls=[{"control_id": "x", "passed": True, "blocking": False}],
        reproducibility_results=[{"cell_id": "a", "comparison_status": "EXACT_MATCH"}],
        cell_results=[
            {
                "cell_id": "penny:s1:factor",
                "status": "succeeded",
                "coverage": {"symbol_count": 4, "date_count": 30},
                "acceptance_status": "FAIL",
                "factor_role": "candidate",
                "factor_key": "staging_momentum_20d",
            }
        ],
    )
    assert gate["status"] == "READY_FOR_PROMOTION_REVIEW"
    assert "staging_momentum_20d" in gate["weak_factors"]


def test_negative_controls_on_fixture_panel(isolated_backend_env, monkeypatch):
    seed_staging_fixture(variant="long_history")
    monkeypatch.setattr(config, "FACTOR_RESEARCH_DATA_PROVIDER", "historical_store", raising=False)
    monkeypatch.setattr(config, "APP_ENV", "test", raising=False)
    from services.factor_discovery.data_provider import get_runtime_factor_research_provider
    from services.factor_discovery.historical_store_provider import assess_historical_store_capabilities

    provider = get_runtime_factor_research_provider()
    caps = assess_historical_store_capabilities()
    panel, _ = provider.load_snapshot(
        start_session="2020-01-02",
        end_session="2020-03-01",
        required_fields={"adjusted_close", "volume"},
        provider_data_version=caps.provider_data_version,
    )
    results = ExtendedStagingNegativeControls().run_all(panel, cut_date="2020-01-15")
    blocking = [r for r in results if r.blocking and not r.passed]
    assert not blocking


def test_artifact_persistence(tmp_path):
    store = ExtendedStagingArtifactStore(output_root=tmp_path)
    report = {"staging_run_id": "ext_test123", "promotion_readiness": {"status": "NOT_READY_FOR_PROMOTION_REVIEW"}}
    path = store.persist(report)
    assert path.exists()
    latest = store.latest()
    assert latest["staging_run_id"] == "ext_test123"


def test_legacy_medium_maps_to_penny_not_restored():
    assert normalize_sleeve("medium") == "penny"
    assert normalize_sleeve("penny") == "penny"
