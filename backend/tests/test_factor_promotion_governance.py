"""Phase 10 promotion governance and shadow scoring safety tests."""
from __future__ import annotations

import json
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
from services.factor_discovery.promotion.evidence_bundle import FactorPromotionEvidenceService
from services.factor_discovery.promotion.gate_service import FactorPromotionGateService
from services.factor_discovery.promotion.lifecycle import validate_transition
from services.factor_discovery.promotion.shadow_scoring import FactorShadowScoringService
from services.factor_discovery.staging.extended_staging_artifact import ExtendedStagingArtifactStore
from tests.fixtures.factor_discovery.persistence_helpers import enable_factor_discovery, seed_family_and_definition


def _enable_promotion(monkeypatch) -> None:
    enable_factor_discovery(monkeypatch)
    monkeypatch.setattr(config, "FACTOR_PROMOTION_GOVERNANCE_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "FACTOR_SHADOW_SCORING_ENABLED", True, raising=False)
    monkeypatch.setattr(config, "QUANT_LAB_RESEARCH_API_ENABLED", True, raising=False)


def _seed_staging_report(tmp_path: Path, *, status: str = "READY_FOR_PROMOTION_REVIEW") -> str:
    store = ExtendedStagingArtifactStore(output_root=tmp_path)
    run_id = "extstage_test_promo"
    report = {
        "staging_run_id": run_id,
        "promotion_readiness": {"status": status, "blocking_findings": [], "weak_factors": ["staging_momentum_20d"]},
        "reproducibility_results": [{"cell_id": "penny:s1:f", "comparison_status": "EXACT_MATCH"}],
        "negative_controls": [{"control_id": "shuffle", "passed": True, "blocking": False}],
        "manifest": {"staging_run_id": run_id, "date_range": {"start": "2020-01-02", "end": "2020-06-01"}},
        "cell_results": [
            {
                "cell_id": "penny:early:staging_momentum_20d",
                "sleeve": "penny",
                "factor_id": "staging_momentum_20d",
                "factor_role": "candidate",
                "acceptance_status": "FAIL",
                "status": "succeeded",
                "run_id": "fdrun_test1",
                "slice_id": "early",
                "coverage": {"symbol_count": 5, "date_count": 40, "valid_cross_sectional_dates": 40},
                "diagnostics": {
                    "factor_id": "staging_momentum_20d",
                    "acceptance_status": "FAIL",
                    "observation_count": {"status": "ok", "value": 5},
                    "mean_rank_ic": {"status": "ok", "value": 0.02},
                    "formula_hash": "sha256:abc",
                    "panel_hash": "sha256:def",
                },
            },
            {
                "cell_id": "penny:early:baseline",
                "sleeve": "penny",
                "factor_id": "baseline_momentum",
                "factor_role": "baseline",
                "acceptance_status": "PASS",
                "status": "succeeded",
                "coverage": {"symbol_count": 5, "date_count": 40},
            },
        ],
    }
    store.persist(report)
    return run_id


def test_illegal_status_transition_rejected():
    with pytest.raises(ValueError, match="illegal promotion transition"):
        validate_transition(FactorPromotionStatus.EXPERIMENTAL, FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION)


def test_gate_evaluation_keeps_failed_gates_visible():
    gate = FactorPromotionGateService().evaluate(
        diagnostics={
            "observation_count": {"status": "ok", "value": 5},
            "date_coverage": {"status": "not_applicable", "reason": "missing"},
            "symbol_coverage": {"status": "not_applicable", "reason": "missing"},
            "coverage": {"valid_cross_sectional_dates": 5},
            "mean_rank_ic": {"status": "ok", "value": -0.05},
        },
        staging_report={"promotion_readiness": {"blocking_findings": []}, "reproducibility_results": [], "negative_controls": []},
        sleeve="penny",
    )
    failed = [g for g in gate.gates if g.verdict.value == "fail"]
    assert failed
    assert any(g.gate_id == "sufficient_observations" for g in failed)


def test_evidence_bundle_immutable(tmp_path):
    from models.schemas_factor_promotion import PromotionGateEvaluation
    from datetime import datetime, timezone

    svc = FactorPromotionEvidenceService(output_root=tmp_path)
    gate = PromotionGateEvaluation(
        policy_id="factor_promotion_gates_v1",
        policy_version="1.0.0",
        evaluated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        overall_pass=False,
        blocking_failures=["sufficient_symbol_coverage"],
        gates=[],
    )
    _, bundle_hash, _ = svc.build_bundle(
        candidate_id="fpcand_test",
        factor_definition={"factor_id": "f1", "sleeve": "penny", "display_name": "Test"},
        diagnostics={"acceptance_status": "FAIL"},
        gate_evaluation=gate,
    )
    bundle_id = list(tmp_path.glob("fpev_*.json"))[0].stem
    detail = svc.load(bundle_id)
    assert detail.bundle_hash == bundle_hash
    path = tmp_path / f"{bundle_id}.json"
    raw = json.loads(path.read_text())
    raw["bundle_hash"] = "tampered"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="integrity mismatch"):
        svc.load(bundle_id)


def test_create_candidate_does_not_modify_live_weights(isolated_backend_env, monkeypatch, tmp_path):
    _enable_promotion(monkeypatch)
    init_quant_db()
    seed_family_and_definition(factor_id="staging_momentum_20d", dsl="rank(relative_volume)")
    run_id = _seed_staging_report(tmp_path)

    monkeypatch.setattr(
        FactorPromotionEvidenceService,
        "__init__",
        lambda self, output_root=None: setattr(self, "_root", tmp_path) or tmp_path.mkdir(exist_ok=True),
    )

    from sqlalchemy.orm import Session
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    with Session(get_engine()) as session:
        before = session.query(FactorWeight).count()

    svc = FactorPromotionCandidateService()
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)
    monkeypatch.setattr(
        svc._evidence,
        "load_staging_report",
        lambda staging_run_id: json.loads((tmp_path / f"extended_staging_{run_id}.json").read_text()),
    )

    detail = svc.create(
        CreatePromotionCandidateRequest(
            factor_id="staging_momentum_20d",
            factor_version="1.0.0",
            sleeve="penny",
            source_staging_run_id=run_id,
            actor="test",
        )
    )
    assert detail.status == FactorPromotionStatus.EXPERIMENTAL
    assert detail.affects_live_ranking is False

    with Session(get_engine()) as session:
        after = session.query(FactorWeight).count()
    assert before == after


def test_approval_blocked_when_gates_fail(isolated_backend_env, monkeypatch, tmp_path):
    _enable_promotion(monkeypatch)
    init_quant_db()
    seed_family_and_definition(factor_id="staging_momentum_20d", dsl="rank(relative_volume)")
    run_id = _seed_staging_report(tmp_path)

    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    svc = FactorPromotionCandidateService()
    monkeypatch.setattr(
        svc._evidence,
        "load_staging_report",
        lambda staging_run_id: json.loads((tmp_path / f"extended_staging_{run_id}.json").read_text()),
    )
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)

    detail = svc.create(
        CreatePromotionCandidateRequest(
            factor_id="staging_momentum_20d",
            factor_version="1.0.0",
            sleeve="penny",
            source_staging_run_id=run_id,
        )
    )
    for status in (
        FactorPromotionStatus.STAGED,
        FactorPromotionStatus.PROMOTION_CANDIDATE,
        FactorPromotionStatus.SHADOW,
    ):
        svc.transition(
            detail.candidate_id,
            PromotionStatusTransitionRequest(target_status=status, actor="reviewer", reason="advance"),
        )

    with pytest.raises(FactorDiscoveryError) as exc:
        svc.transition(
            detail.candidate_id,
            PromotionStatusTransitionRequest(
                target_status=FactorPromotionStatus.APPROVED_FOR_MANUAL_INTEGRATION,
                actor="reviewer",
                reason="approve",
            ),
        )
    assert exc.value.code == "GATES_NOT_PASS"


def test_sleeve_normalization_blocks_medium_restore():
    assert normalize_sleeve("medium") == "penny"
    assert normalize_sleeve("compounder") == "compounder"


def test_shadow_scoring_preserves_live_score(monkeypatch):
    import pandas as pd
    from engines.scoring.engine import ScoringEngine
    from screeners.base import CandidateContext, WeightedSignal

    monkeypatch.setattr(
        "engines.scoring.engine.apply_regime_to_score",
        lambda raw, *args, **kwargs: (raw, {"final_multiplier": 1.0, "sector_regime": {"tilt": 0.0}}),
    )
    monkeypatch.setattr(
        "services.scan_scoring._apply_openbb_adjustment",
        lambda score, metrics: score,
    )

    hist = pd.DataFrame({"Close": [10, 10.5, 11, 11.2, 11.5], "Volume": [1e6] * 5})
    ctx = CandidateContext(symbol="TEST", price=11.5, info={"sector": "Tech", "momentum_5d": 0.05}, history=hist)

    live = ScoringEngine.score(ctx, "penny", apply_openbb=False)
    live_before = live.final_score
    signals = list(live.signals)
    signals.append(WeightedSignal(name="shadow:test", value=80.0, weight=0.05, description="shadow"))
    from engines.factor.engine import FactorEngine

    shadow_score = FactorEngine.composite_score(signals)
    live_after = ScoringEngine.score(ctx, "penny", apply_openbb=False).final_score
    assert len(signals) > len(live.signals)
    assert live_before == live_after
    assert shadow_score != live.raw_score


def test_explain_does_not_change_status(isolated_backend_env, monkeypatch, tmp_path):
    _enable_promotion(monkeypatch)
    init_quant_db()
    seed_family_and_definition(factor_id="staging_momentum_20d", dsl="rank(relative_volume)")
    run_id = _seed_staging_report(tmp_path)

    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    svc = FactorPromotionCandidateService()
    monkeypatch.setattr(
        svc._evidence,
        "load_staging_report",
        lambda staging_run_id: json.loads((tmp_path / f"extended_staging_{run_id}.json").read_text()),
    )
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)

    detail = svc.create(
        CreatePromotionCandidateRequest(
            factor_id="staging_momentum_20d",
            factor_version="1.0.0",
            sleeve="penny",
            source_staging_run_id=run_id,
        )
    )
    explained = svc.explain(detail.candidate_id)
    assert explained["gates_unchanged"] is True
    assert explained["status_unchanged"] is True
    refreshed = svc.get(detail.candidate_id)
    assert refreshed.status == FactorPromotionStatus.EXPERIMENTAL


def test_promotion_api_disabled_without_flag(isolated_backend_env, monkeypatch):
    monkeypatch.setattr(config, "FACTOR_PROMOTION_GOVERNANCE_ENABLED", False, raising=False)
    monkeypatch.setattr(config, "QUANT_LAB_RESEARCH_API_ENABLED", True, raising=False)
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    resp = client.get("/api/v2/research/factor-discovery/promotion-candidates")
    assert resp.status_code == 503


def test_stale_evidence_cannot_approve(isolated_backend_env, monkeypatch, tmp_path):
    _enable_promotion(monkeypatch)
    init_quant_db()
    seed_family_and_definition(factor_id="staging_momentum_20d", dsl="rank(relative_volume)")
    run_id = _seed_staging_report(tmp_path)

    from services.factor_discovery.errors import FactorDiscoveryError
    from services.factor_discovery.promotion.candidate_service import FactorPromotionCandidateService

    svc = FactorPromotionCandidateService()
    monkeypatch.setattr(
        svc._evidence,
        "load_staging_report",
        lambda staging_run_id: json.loads((tmp_path / f"extended_staging_{run_id}.json").read_text()),
    )
    monkeypatch.setattr(svc._evidence, "_root", tmp_path)

    detail = svc.create(
        CreatePromotionCandidateRequest(
            factor_id="staging_momentum_20d",
            factor_version="1.0.0",
            sleeve="penny",
            source_staging_run_id=run_id,
        )
    )
    with pytest.raises(FactorDiscoveryError) as exc:
        svc.transition(
            detail.candidate_id,
            PromotionStatusTransitionRequest(
                target_status=FactorPromotionStatus.STAGED,
                actor="reviewer",
                reason="advance",
                expected_evidence_bundle_hash="sha256:wrong",
            ),
        )
    assert exc.value.code == "STALE_EVIDENCE"
