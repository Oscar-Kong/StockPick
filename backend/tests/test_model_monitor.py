"""Phase 6 — model monitor, evidence review, decision boundary."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from data.db_engine import get_engine
from models.schemas_research import ChangeProposalCreate, EvidenceReviewActionRequest
from services.change_proposals_service import create_proposal
from services.evidence_impact_policy import apply_ordinary_modifier_to_score, evaluate_evidence_impact
from services.evidence_impact_review_service import apply_review_action, list_review_findings
from services.job_retry_service import retry_research_job
from services.model_monitor_service import get_model_monitor
from services.research_decision_boundary import apply_research_evidence_to_score
from services.research_run_service import adapter_walk_forward, upsert_run_index
from tests.fixtures.quant_lab_fixtures import seed_job_queue, seed_walk_forward_run


@pytest.fixture
def research_db(isolated_backend_env):
    init_quant_db()
    return isolated_backend_env


@pytest.fixture
def client(research_db):
    try:
        from fastapi.testclient import TestClient
        from main import app

        return TestClient(app)
    except RuntimeError as exc:
        if "httpx" in str(exc):
            pytest.skip("httpx not installed")
        raise


def test_model_monitor_sections(research_db):
    seed_walk_forward_run()
    summary = adapter_walk_forward("wf_test_001")
    assert summary
    upsert_run_index(summary)
    mon = get_model_monitor("penny")
    assert mon.sleeve == "penny"
    assert isinstance(mon.factor_health, list)
    assert mon.prediction_health.resolved_count >= 0
    assert mon.model_configuration.strategy_version


def test_job_retry_duplicate_blocked(research_db, monkeypatch):
    failed_id = seed_job_queue(status="failed", job_name="quant_daily_jobs")
    engine = get_engine()
    from engines.quant_models import JobQueueItem
    from sqlalchemy.orm import Session

    pending_id = "job_pending_dup"
    with Session(engine) as session:
        session.add(
            JobQueueItem(
                job_id=pending_id,
                job_name="quant_daily_jobs",
                payload_json="{}",
                status="pending",
                strategy_version="test_v1",
                factor_model_version="test_f1",
            )
        )
        session.commit()

    blocked = retry_research_job(failed_id)
    assert blocked.duplicate_blocked is True
    assert "duplicate" in blocked.message


def test_evidence_review_list_and_action(research_db):
    seed_walk_forward_run()
    s = adapter_walk_forward("wf_test_001")
    assert s
    s.evidence_impact = "supporting"
    upsert_run_index(s)
    findings = list_review_findings(sleeve="penny")
    assert findings.total >= 1
    fid = findings.findings[0].finding_id
    result = apply_review_action(
        fid,
        EvidenceReviewActionRequest(action="leave_informational", notes="review test"),
    )
    assert result is not None
    assert result.evidence_impact == "informational"


def test_major_gate_pass_and_fail(research_db):
    from services.major_evidence_gate import evaluate_major_evidence_gate

    pass_gate = evaluate_major_evidence_gate(
        run_type="walk_forward",
        summary={
            "periods_scored": 50,
            "end_date": "2024-01-01",
            "aggregate_horizons": {"20": {"mean_rank_ic": 0.08}},
            "sample_size": 50,
        },
        parameters={"sleeve": "penny", "end_date": "2024-01-01"},
    )
    assert pass_gate.impact_level in ("major_positive", "major_negative", "informational")

    fail_gate = evaluate_major_evidence_gate(
        run_type="walk_forward",
        summary={"periods_scored": 1, "aggregate_horizons": {}},
        parameters={},
        blockers=["explicit_blocker:test"],
    )
    assert fail_gate.blocking_checks


def test_change_proposal_workflow(research_db):
    prop = create_proposal(
        ChangeProposalCreate(
            title="Test proposal",
            finding="Factor weight tweak",
            supporting_run_ids=["wf_test_001"],
            status="draft",
        )
    )
    assert prop.id.startswith("cp_")
    assert prop.status == "draft"


def test_default_no_impact_on_score(research_db, monkeypatch):
    import config

    monkeypatch.setattr(config, "RESEARCH_MAX_ORDINARY_MODIFIER", 0.0)
    ev = evaluate_evidence_impact(proposed_impact="supporting")
    assert apply_ordinary_modifier_to_score(75.0, ev) == 75.0
    consumption = apply_research_evidence_to_score(75.0, symbol="AAPL", sleeve="penny", audit=False)
    assert consumption.adjusted_score == 75.0


def test_capped_supporting_modifier(research_db, monkeypatch):
    import services.evidence_impact_policy as policy

    monkeypatch.setattr(policy, "RESEARCH_MAX_ORDINARY_MODIFIER", 2.0)
    ev = policy.evaluate_evidence_impact(proposed_impact="supporting")
    assert policy.apply_ordinary_modifier_to_score(75.0, ev) == 77.0


def test_integrity_blocker_no_positive_modifier(research_db):
    ev = evaluate_evidence_impact(proposed_impact="integrity_blocker", integrity_blocked=True)
    assert apply_ordinary_modifier_to_score(75.0, ev) == 75.0


def test_audit_record_on_score_consumption(research_db):
    from engines.audit.logger import list_audit_logs

    apply_research_evidence_to_score(80.0, symbol="MSFT", sleeve="penny", audit=True)
    events = list_audit_logs(limit=5, event_type="research_evidence_consumed", symbol="MSFT")
    assert len(events) >= 1


def test_api_model_monitor_and_review(client, research_db):
    seed_walk_forward_run()
    upsert_run_index(adapter_walk_forward("wf_test_001"))
    r = client.get("/api/v2/research/model-monitor?sleeve=penny")
    assert r.status_code == 200
    rev = client.get("/api/v2/research/evidence-review?sleeve=penny")
    assert rev.status_code == 200


def test_production_weight_unchanged_by_experiment(research_db, monkeypatch):
    """Successful experiment indexing must not mutate WeightStore."""
    from engines.weighting.weight_store import WeightStore

    seed_walk_forward_run()
    upsert_run_index(adapter_walk_forward("wf_test_001"))
    before = dict(WeightStore.load("penny"))
    upsert_run_index(adapter_walk_forward("wf_test_001"))
    after = dict(WeightStore.load("penny"))
    assert before == after
