"""Backend tests for research overview and brief idea rules."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_research import GenerateIdeasRequest, ResearchIdeaCreate
from services.research_brief_service import build_research_brief
from services.research_idea_generation_service import duplicate_idea, generate_ideas_from_findings
from services.research_ideas_service import create_idea, list_ideas
from services.research_overview_service import get_research_overview
from tests.fixtures.quant_lab_fixtures import seed_factor_ic, seed_walk_forward_run


@pytest.fixture
def research_db(isolated_backend_env):
    init_quant_db()
    return isolated_backend_env


@pytest.fixture
def client(research_db):
    from fastapi.testclient import TestClient
    from main import app

    return TestClient(app)


def test_overview_empty_database(research_db):
    overview = get_research_overview("penny")
    assert overview.sleeve == "penny"
    assert overview.research_confidence_score >= 0
    assert isinstance(overview.findings, list)
    assert isinstance(overview.maintenance_actions, list)
    assert len(overview.maintenance_actions) >= 1


def test_overview_with_seeded_evidence(research_db):
    seed_factor_ic(sleeve="penny")
    seed_walk_forward_run()
    overview = get_research_overview("penny")
    assert overview.factor_ic is not None
    assert overview.factor_ic.available is True
    assert overview.walk_forward is not None


def test_brief_ic_drift_finding(research_db):
    seed_factor_ic(sleeve="penny", as_of=date.today())
    findings = build_research_brief(
        sleeve="penny",
        factor_ic_rows=[
            {"factor_id": "momentum", "horizon_days": 20, "ic": 0.12, "sample_n": 150},
        ],
        factor_ic_history=[
            {"factor_id": "momentum", "horizon_days": 20, "ic": 0.02, "sample_n": 120},
            {"factor_id": "momentum", "horizon_days": 20, "ic": 0.03, "sample_n": 110},
            {"factor_id": "momentum", "horizon_days": 20, "ic": 0.01, "sample_n": 100},
        ],
        walk_forward=None,
        pairs_summary=None,
        predictions_resolved=10,
        predictions_unresolved=2,
        feedback_by_rec={},
        data_freshness="fresh",
        factor_ic_stale=False,
        walk_forward_stale=False,
        jobs_failed=0,
    )
    assert any(
        "drift" in f.title.lower()
        or "differs" in f.title.lower()
        or "differs" in f.explanation.lower()
        or "improved" in f.title.lower()
        or "deteriorated" in f.title.lower()
        for f in findings
    )


def test_brief_skips_when_data_absent(research_db):
    findings = build_research_brief(
        sleeve="penny",
        factor_ic_rows=[],
        factor_ic_history=[],
        walk_forward=None,
        pairs_summary=None,
        predictions_resolved=0,
        predictions_unresolved=0,
        feedback_by_rec={},
        data_freshness="fresh",
        factor_ic_stale=False,
        walk_forward_stale=False,
        jobs_failed=0,
    )
    assert findings == []


def test_generate_ideas_dedup(research_db):
    overview = get_research_overview("penny")
    if not overview.findings:
        overview.findings = [
            __import__("models.schemas_research", fromlist=["ResearchBriefFinding"]).ResearchBriefFinding(
                finding_id="finding_test_001",
                title="Test stale IC panel",
                explanation="IC is old",
                supporting_metric="age=30d",
                source_reference="factor_ic_history",
                why_it_matters="Need refresh",
                confidence=0.8,
                evidence_impact="informational",
                suggested_experiment_type="factor_validation",
                suggested_parameters={"sleeve": "penny"},
            )
        ]
    first = generate_ideas_from_findings(overview.findings, sleeve="penny", limit=5)
    assert len(first.created) >= 1
    second = generate_ideas_from_findings(overview.findings, sleeve="penny", limit=5)
    assert second.skipped_duplicates >= 1


def test_duplicate_idea(research_db):
    idea = create_idea(ResearchIdeaCreate(title="Original", hypothesis="test"))
    dup = duplicate_idea(idea.id)
    assert dup is not None
    assert dup.id != idea.id
    assert "copy" in dup.title.lower()


def test_overview_api_contract(client):
    r = client.get("/api/v2/research/overview?sleeve=penny")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in (
        "research_confidence_status",
        "findings",
        "recommended_ideas",
        "recent_activity",
        "maintenance_actions",
        "strategy_version",
    ):
        assert key in body


def test_generate_ideas_api(client, research_db):
    r = client.post("/api/v2/research/ideas/generate", json={"sleeve": "penny", "limit": 3})
    assert r.status_code == 200, r.text
    assert "created" in r.json()
