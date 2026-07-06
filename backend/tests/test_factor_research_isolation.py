"""Phase 11 research→production isolation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from core.sleeve import normalize_sleeve
from data.db_engine import get_engine
from engines.quant_db import init_quant_db
from engines.quant_models import FactorWeight
from models.schemas_factor_promotion import (
    CreatePromotionCandidateRequest,
    FactorPromotionStatus,
    PromotionStatusTransitionRequest,
)
from services.factor_discovery.isolation_audit import verify_research_isolation
from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService
from services.factor_discovery.promotion.lifecycle import validate_transition
from services.factor_discovery.errors import ProductionPromotionError, FactorDiscoveryError
from services.factor_discovery.lifecycle_service import FactorLifecycleService, LifecycleTransitionRequest
from models.schemas_factor_discovery import FactorLifecycleStatus
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition


def test_isolation_audit_no_production_write_paths():
    result = verify_research_isolation()
    assert not result["blockers"]
    assert "scan_adapter" in str(result["write_paths_absent"])
    assert result["advisory_only"] is True


def test_lifecycle_production_transition_blocked():
    with pytest.raises(ProductionPromotionError):
        FactorLifecycleService().transition(
            LifecycleTransitionRequest(
                factor_id="probe",
                factor_version="1.0.0",
                target_status=FactorLifecycleStatus.PRODUCTION,
                actor_type="system",
                actor_identifier="test",
                reason="isolation test",
            )
        )


def test_research_runs_cannot_skip_to_production_promotion():
    with pytest.raises(ValueError):
        validate_transition(FactorPromotionStatus.EXPERIMENTAL, FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION)


def test_candidate_approval_does_not_modify_weights(isolated_backend_env, monkeypatch, tmp_path):
    import json

    enable_factor_discovery(monkeypatch)
    monkeypatch.setattr(config, "FACTOR_PROMOTION_GOVERNANCE_ENABLED", True, raising=False)
    init_quant_db()
    seed_family_and_definition(factor_id="iso_factor", dsl="rank(relative_volume)")

    run_id = "extstage_iso_test"
    staging_dir = tmp_path / "staging"
    staging_dir.mkdir()
    report = {
        "staging_run_id": run_id,
        "promotion_readiness": {"status": "READY_FOR_PROMOTION_REVIEW", "blocking_findings": [], "weak_factors": []},
        "reproducibility_results": [{"comparison_status": "EXACT_MATCH"}],
        "negative_controls": [{"passed": True, "blocking": False}],
        "cell_results": [{
            "sleeve": "penny", "factor_id": "iso_factor", "factor_role": "candidate",
            "acceptance_status": "FAIL", "status": "succeeded", "run_id": "r1", "slice_id": "s1",
            "coverage": {"symbol_count": 5, "date_count": 40, "valid_cross_sectional_dates": 40},
            "diagnostics": {"factor_id": "iso_factor", "observation_count": {"value": 5},
                            "formula_hash": "sha256:a", "panel_hash": "sha256:b"},
        }],
    }
    (staging_dir / f"extended_staging_{run_id}.json").write_text(json.dumps(report))

    from sqlalchemy.orm import Session

    svc = FactorPromotionCandidateService()
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)
    monkeypatch.setattr(svc._evidence, "load_staging_report", lambda rid: report)

    with Session(get_engine()) as session:
        before = session.query(FactorWeight).count()

    detail = svc.create(CreatePromotionCandidateRequest(
        factor_id="iso_factor", factor_version="1.0.0", sleeve="penny", source_staging_run_id=run_id,
    ))
    for status in (FactorPromotionStatus.STAGED, FactorPromotionStatus.PROMOTION_CANDIDATE, FactorPromotionStatus.SHADOW):
        svc.transition(detail.candidate_id, PromotionStatusTransitionRequest(
            target_status=status, actor="test", reason="advance",
        ))

    with Session(get_engine()) as session:
        after = session.query(FactorWeight).count()
    assert before == after


def test_malformed_transition_rejected(isolated_backend_env, monkeypatch, tmp_path):
    enable_factor_discovery(monkeypatch)
    monkeypatch.setattr(config, "FACTOR_PROMOTION_GOVERNANCE_ENABLED", True, raising=False)
    init_quant_db()
    seed_family_and_definition(factor_id="iso_factor2", dsl="rank(relative_volume)")

    svc = FactorPromotionCandidateService()
    report = {
        "staging_run_id": "x", "promotion_readiness": {"status": "READY_FOR_PROMOTION_REVIEW"},
        "reproducibility_results": [], "negative_controls": [],
        "cell_results": [{"sleeve": "penny", "factor_id": "iso_factor2", "factor_role": "candidate",
                          "diagnostics": {"observation_count": {"value": 5}}, "coverage": {"symbol_count": 5, "date_count": 40}}],
    }
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)
    monkeypatch.setattr(svc._evidence, "load_staging_report", lambda _: report)

    detail = svc.create(CreatePromotionCandidateRequest(
        factor_id="iso_factor2", factor_version="1.0.0", sleeve="penny",
    ))
    with pytest.raises(ValueError):
        svc.transition(detail.candidate_id, PromotionStatusTransitionRequest(
            target_status=FactorPromotionStatus.SHADOW, actor="test", reason="skip stages",
        ))


def test_sleeve_isolation_medium_maps_to_penny_not_compounder():
    assert normalize_sleeve("medium") == "penny"
    assert normalize_sleeve("compounder") == "compounder"


def test_duplicate_status_transition_idempotent_on_same_status(isolated_backend_env, monkeypatch, tmp_path):
    """Same-status transition is a no-op at lifecycle level; promotion service rejects illegal jumps."""
    enable_factor_discovery(monkeypatch)
    monkeypatch.setattr(config, "FACTOR_PROMOTION_GOVERNANCE_ENABLED", True, raising=False)
    init_quant_db()
    seed_family_and_definition(factor_id="iso_factor3", dsl="rank(relative_volume)")
    svc = FactorPromotionCandidateService()
    report = {
        "staging_run_id": "x", "promotion_readiness": {"status": "READY_FOR_PROMOTION_REVIEW"},
        "reproducibility_results": [], "negative_controls": [],
        "cell_results": [{"sleeve": "compounder", "factor_id": "iso_factor3", "factor_role": "candidate",
                          "diagnostics": {"observation_count": {"value": 5}}, "coverage": {"symbol_count": 5, "date_count": 40}}],
    }
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)
    monkeypatch.setattr(svc._evidence, "load_staging_report", lambda _: report)
    detail = svc.create(CreatePromotionCandidateRequest(
        factor_id="iso_factor3", factor_version="1.0.0", sleeve="compounder",
    ))
    r1 = svc.transition(detail.candidate_id, PromotionStatusTransitionRequest(
        target_status=FactorPromotionStatus.STAGED, actor="test", reason="once",
    ))
    with pytest.raises(FactorDiscoveryError) as exc:
        svc.transition(detail.candidate_id, PromotionStatusTransitionRequest(
            target_status=FactorPromotionStatus.STAGED, actor="test", reason="duplicate",
        ))
    assert exc.value.code == "NO_OP_TRANSITION"
