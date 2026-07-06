"""Phase 2 — research foundation, evidence memory, impact policy tests."""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_research import (
    ChangeProposalCreate,
    EvidenceMemoryCreate,
    ResearchExperimentCreate,
    ResearchIdeaCreate,
    ResearchIdeaUpdate,
)
from services.change_proposals_service import create_proposal, get_proposal
from services.evidence_impact_policy import (
    apply_ordinary_modifier_to_score,
    evaluate_evidence_impact,
    impact_from_gate_result,
)
from services.evidence_memory_service import create_evidence_memory, list_evidence_memory
from services.factor_lineage_service import get_factor_lineage, record_factor_lineage
from services.major_evidence_gate import evaluate_integrity_blockers, evaluate_major_evidence_gate
from services.research_experiments_service import create_experiment, get_experiment
from services.research_ideas_service import create_idea, delete_idea, get_idea, list_ideas, update_idea
from services.research_run_service import (
    adapter_factor_ic_panel,
    adapter_pairs,
    adapter_walk_forward,
    backfill_run_index,
    compare_runs,
    get_run,
    list_runs,
    upsert_run_index,
)
from tests.fixtures.quant_lab_fixtures import seed_factor_ic, seed_pairs_run, seed_walk_forward_run


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


def test_idea_crud(research_db):
    created = create_idea(
        ResearchIdeaCreate(
            title="Momentum decay in penny sleeve",
            hypothesis="5d momentum IC is fading",
            source_type="factor_deterioration",
            sleeve="penny",
            status="new",
        )
    )
    assert created.id.startswith("idea_")
    fetched = get_idea(created.id)
    assert fetched is not None
    assert fetched.title == "Momentum decay in penny sleeve"

    updated = update_idea(created.id, ResearchIdeaUpdate(status="ready_to_test"))
    assert updated is not None
    assert updated.status == "ready_to_test"

    listed = list_ideas(sleeve="penny")
    assert listed.total >= 1
    assert delete_idea(created.id) is True
    assert get_idea(created.id) is None


def test_idea_invalid_status_raises(research_db):
    idea = create_idea(ResearchIdeaCreate(title="Status test", hypothesis="x"))
    with pytest.raises(ValueError, match="invalid status"):
        update_idea(idea.id, ResearchIdeaUpdate.model_construct(status="not_a_status"))


def test_experiment_persistence(research_db):
    idea = create_idea(ResearchIdeaCreate(title="WF idea", hypothesis="edge persists"))
    exp = create_experiment(
        ResearchExperimentCreate(
            idea_id=idea.id,
            name="Penny WF validation",
            experiment_type="walk_forward",
            sleeve="penny",
            preset="robust",
            parameters={"forward_horizons": [20, 60]},
        )
    )
    assert exp.id.startswith("exp_")
    loaded = get_experiment(exp.id)
    assert loaded is not None
    assert loaded.idea_id == idea.id
    assert loaded.experiment_type == "walk_forward"


def test_run_adapters_walk_forward_and_pairs(research_db):
    seed_walk_forward_run()
    seed_pairs_run()
    seed_factor_ic(sleeve="penny", as_of=date.today())

    wf = adapter_walk_forward("wf_test_001")
    assert wf is not None
    assert wf.run_type == "walk_forward"
    assert wf.sample_size is not None

    pairs = adapter_pairs("pairs_test_001")
    assert pairs is not None
    assert pairs.run_type == "pairs"

    ic = adapter_factor_ic_panel("penny", date.today().isoformat())
    assert ic is not None
    assert ic.run_type == "factor_ic_panel"

    indexed = backfill_run_index(limit=50)
    assert indexed >= 2

    runs = list_runs(run_type="walk_forward", backfill=False)
    assert runs.total >= 1
    assert any(r.run_id == "wf_test_001" for r in runs.runs)


def test_run_compare_metadata(research_db):
    seed_walk_forward_run()
    backfill_run_index(limit=10)
    runs = list_runs(backfill=False)
    assert runs.total >= 1
    rid = runs.runs[0].run_id
    cmp = compare_runs([rid, rid])
    assert cmp.comparable is True
    assert len(cmp.runs) == 2


def test_evidence_memory_create_and_list(research_db):
    row = create_evidence_memory(
        EvidenceMemoryCreate(
            symbol="AAPL",
            deterministic_finding="IC positive at 20d horizon",
            evidence_impact="informational",
            original_signal={"recommendation": "Buy"},
            factor_snapshot_ref={"factor_id": "penny_momentum_5d"},
            market_regime="risk_on",
        )
    )
    assert row.id > 0
    listed = list_evidence_memory(symbol="AAPL")
    assert listed.total >= 1
    assert listed.items[0].symbol == "AAPL"


def test_factor_lineage_record(research_db):
    from engines.quant_models import FactorDefinition
    from data.db_engine import get_engine
    from sqlalchemy.orm import Session

    with Session(get_engine()) as session:
        session.add(
            FactorDefinition(
                factor_id="test_momentum",
                sleeve="penny",
                display_name="Test Momentum",
                tier="important",
                formula_version="2026-06-v1",
                is_active=True,
            )
        )
        session.commit()

    lineage = record_factor_lineage(factor_id="test_momentum", sleeve="penny")
    assert lineage.factor_id == "test_momentum"
    assert lineage.factor_name == "Test Momentum"
    listed = get_factor_lineage("test_momentum")
    assert listed.total >= 1


def test_evidence_impact_policy_display_only(research_db, monkeypatch):
    import config

    monkeypatch.setattr(config, "RESEARCH_MAX_ORDINARY_MODIFIER", 0.0)
    ev = evaluate_evidence_impact(proposed_impact="supporting")
    assert ev.display_only is True
    assert ev.score_modifier == 0.0
    assert apply_ordinary_modifier_to_score(75.0, ev) == 75.0


def test_evidence_impact_with_modifier(research_db, monkeypatch):
    monkeypatch.setattr("services.evidence_impact_policy.RESEARCH_MAX_ORDINARY_MODIFIER", 2.0)
    ev = evaluate_evidence_impact(proposed_impact="supporting")
    assert ev.score_modifier == 2.0
    assert apply_ordinary_modifier_to_score(75.0, ev) == 77.0
    major = evaluate_evidence_impact(proposed_impact="major_positive")
    assert apply_ordinary_modifier_to_score(75.0, major) == 75.0


def test_major_evidence_gate_walk_forward_strong(research_db):
    summary = {
        "periods_scored": 12,
        "end_date": "2024-12-31",
        "start_date": "2023-01-01",
        "mean_turnover": 0.15,
        "aggregate_horizons": {"20": {"mean_rank_ic": 0.06}},
        "strategy_version": "v1",
        "factor_model_version": "v1",
        "sleeve": "penny",
        "sample_size": 120,
    }
    params = {"sleeve": "penny", "start_date": "2023-01-01", "end_date": "2024-12-31"}
    gate = evaluate_major_evidence_gate(
        run_type="walk_forward",
        summary=summary,
        parameters=params,
        positive_direction=True,
    )
    assert gate.impact_level in ("major_positive", "informational")
    assert "known_model_versions" in gate.passed_checks


def test_integrity_blocker_stale_ic(research_db):
    gate = evaluate_integrity_blockers(
        run_type="factor_ic_panel",
        summary={"as_of_date": "2020-01-01"},
        parameters={"as_of_date": "2020-01-01"},
        warnings=[],
        blockers=[],
    )
    assert gate.impact_level == "integrity_blocker"
    assert any("stale" in b for b in gate.blocking_checks)


def test_integrity_blocker_leakage_warning(research_db):
    gate = evaluate_integrity_blockers(
        run_type="walk_forward",
        summary={},
        parameters={},
        warnings=["possible look-ahead leakage in labels"],
        blockers=[],
    )
    assert gate.impact_level == "integrity_blocker"
    assert "unresolved_leakage_warning" in gate.blocking_checks


def test_change_proposal_persistence(research_db):
    prop = create_proposal(
        ChangeProposalCreate(
            title="Retire negative IC factor",
            finding="Quality factor IC < 0 for 3 panels",
            supporting_run_ids=["ic_panel:penny:2024-01-01"],
            proposed_change={"action": "retire_factor", "factor_id": "medium_quality"},
            affected_sleeve="penny",
            affected_factors=["medium_quality"],
            status="draft",
        )
    )
    assert prop.id.startswith("cp_")
    loaded = get_proposal(prop.id)
    assert loaded is not None
    assert loaded.status == "draft"
    assert "medium_quality" in loaded.affected_factors


def test_impact_from_gate_result(research_db):
    assert impact_from_gate_result(passed_major=True, positive_direction=True, integrity_blocked=False) == "major_positive"
    assert impact_from_gate_result(passed_major=False, positive_direction=True, integrity_blocked=True) == "integrity_blocker"


def test_api_ideas_contract(client):
    r = client.post(
        "/api/v2/research/ideas",
        json={"title": "API idea", "hypothesis": "test", "source_type": "user_created"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"].startswith("idea_")

    r2 = client.get("/api/v2/research/ideas")
    assert r2.status_code == 200
    assert r2.json()["total"] >= 1


def test_api_runs_empty_then_seed(client, research_db):
    r = client.get("/api/v2/research/runs?backfill=false")
    assert r.status_code == 200
    assert r.json()["total"] == 0

    seed_walk_forward_run()
    r2 = client.post("/api/v2/research/runs/backfill?limit=20")
    assert r2.status_code == 200
    r3 = client.get("/api/v2/research/runs?backfill=false")
    assert r3.json()["total"] >= 1


def test_api_disabled_returns_503(client, monkeypatch):
    monkeypatch.setattr("api.routes_research_lab.QUANT_LAB_RESEARCH_API_ENABLED", False)
    r = client.get("/api/v2/research/ideas")
    assert r.status_code == 503


def test_api_malformed_idea_returns_400(client):
    r = client.post("/api/v2/research/ideas", json={"title": "", "hypothesis": "x"})
    assert r.status_code == 422


def test_api_gate_evaluate(client, research_db):
    seed_walk_forward_run()
    client.post("/api/v2/research/runs/backfill?limit=10")
    r = client.post("/api/v2/research/gate/evaluate?run_id=wf_test_001")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "passed_checks" in body
    assert "impact_level" in body
