"""Phase 5 — unified results, interpretation, comparison, evidence memory."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_research import ResearchRunFollowUpIdeaRequest, ResearchRunNoteRequest
from services.evidence_memory_sync_service import sync_evidence_from_run, update_later_outcomes
from services.research_run_detail_service import build_charts, get_run_detail
from services.research_run_export_service import export_csv, export_json
from services.research_run_interpretation_service import (
    build_interpretation,
    compute_verdict,
    sanitize_llm_prose,
)
from services.research_run_service import (
    adapter_walk_forward,
    backfill_run_index,
    compare_runs_detail,
    list_runs,
    refresh_run_from_store,
    upsert_run_index,
)
from services.research_results_service import archive_run, set_run_notes
from tests.fixtures.quant_lab_fixtures import seed_pairs_run, seed_walk_forward_run


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


def _index_wf(run_id: str = "wf_test_001") -> None:
    seed_walk_forward_run(run_id=run_id)
    summary = adapter_walk_forward(run_id)
    assert summary
    upsert_run_index(summary)


def test_results_filtering(research_db):
    _index_wf("wf_filter_a")
    _index_wf("wf_filter_b")
    seed_pairs_run(run_id="pairs_filter")
    backfill_run_index(limit=20)

    by_type = list_runs(run_type="walk_forward", backfill=False)
    assert all(r.run_type == "walk_forward" for r in by_type.runs)

    search = list_runs(search="wf_filter_a", backfill=False)
    assert any(r.run_id == "wf_filter_a" for r in search.runs)

    archived = archive_run("wf_filter_a", archived=True)
    assert archived is not None
    assert archived.archived is True
    active = list_runs(backfill=False, archived=False)
    assert not any(r.run_id == "wf_filter_a" for r in active.runs)


def test_result_detail_and_verdict_states(research_db):
    _index_wf()
    detail = get_run_detail("wf_test_001", refresh=True, use_llm=False)
    assert detail is not None
    assert detail.interpretation.verdict in {
        "supports_hypothesis",
        "rejects_hypothesis",
        "inconclusive",
        "insufficient_data",
        "invalid",
    }
    assert detail.interpretation.conclusion
    assert len(detail.interpretation.supporting_observations) <= 3
    assert detail.interpretation.major_evidence_gate.impact_level


@pytest.mark.parametrize(
    "sample,blockers,expected",
    [
        (0, [], "insufficient_data"),
        (100, ["job_failed"], "invalid"),
    ],
)
def test_verdict_edge_cases(research_db, sample, blockers, expected):
    from models.schemas_research import ResearchRunSummary, ResultReference
    from services.major_evidence_gate import evaluate_major_evidence_gate
    from services.research_run_interpretation_service import compute_reliability

    summary = ResearchRunSummary(
        run_id="edge",
        run_type="walk_forward",
        name="edge",
        status="completed",
        sample_size=sample,
        blockers=blockers,
        result_reference=ResultReference(store="backtest_runs", run_id="edge"),
    )
    detail = {"periods_scored": sample, "aggregate_horizons": {"20": {"mean_rank_ic": 0.0}}}
    gate = evaluate_major_evidence_gate(
        run_type="walk_forward",
        summary=detail,
        parameters={},
        blockers=blockers,
    )
    rel = compute_reliability(summary, detail, gate)
    verdict = compute_verdict(summary, detail, gate, rel)
    assert verdict == expected


def test_charts_sparse_data(research_db):
    from models.schemas_research import ResearchRunSummary, ResultReference

    summary = ResearchRunSummary(
        run_id="sparse",
        run_type="walk_forward",
        name="sparse",
        status="completed",
        result_reference=ResultReference(store="backtest_runs", run_id="sparse"),
    )
    charts = build_charts("walk_forward", summary, {"periods": []})
    assert charts
    assert any(c.empty_reason for c in charts)


def test_compare_compatible_and_incompatible(research_db):
    _index_wf("wf_cmp_a")
    _index_wf("wf_cmp_b")
    seed_pairs_run(run_id="pairs_cmp")
    backfill_run_index(limit=10)

    ok = compare_runs_detail(["wf_cmp_a", "wf_cmp_b"])
    assert ok.comparable is True
    assert ok.metric_diffs

    bad = compare_runs_detail(["wf_cmp_a", "pairs_cmp"])
    assert bad.comparable is False
    assert any(c.status == "error" for c in bad.compatibility_checks)


def test_evidence_memory_sync_and_outcomes(research_db):
    seed_pairs_run(run_id="pairs_ev")
    backfill_run_index(limit=5)
    created = sync_evidence_from_run("pairs_ev")
    assert len(created) >= 1
    original = created[0].deterministic_finding
    memory_id = created[0].id
    updated = update_later_outcomes(created[0].run_id or "pairs_ev", {"return_pct": 3.5})
    assert updated
    match = next((u for u in updated if u.id == memory_id), updated[0])
    assert match.deterministic_finding == original
    assert updated[0].forward_outcomes.get("return_pct") == 3.5


def test_export_json_and_csv(research_db):
    _index_wf()
    j = export_json("wf_test_001")
    assert j
    payload = json.loads(j)
    assert payload["verdict"]
    assert "api_key" not in j.lower()
    csv_body = export_csv("wf_test_001")
    assert csv_body
    assert "run_id" in csv_body


def test_refresh_persistence(research_db):
    _index_wf()
    row = refresh_run_from_store("wf_test_001")
    assert row is not None
    assert row.run_id == "wf_test_001"


def test_optional_llm_disabled(research_db, monkeypatch):
    import config

    monkeypatch.setattr(config, "LLM_ENABLED", False)
    _index_wf()
    detail = get_run_detail("wf_test_001", refresh=True, use_llm=False)
    assert detail
    assert detail.interpretation.prose is None


def test_optional_llm_malformed_sanitized(research_db):
    from models.schemas_research import MajorEvidenceGateResult, ResearchRunInterpretation, ResearchRunReliability

    interp = ResearchRunInterpretation(
        verdict="inconclusive",
        conclusion="Base conclusion.",
        evidence_impact="informational",
        reliability=ResearchRunReliability(score=50, status="moderate"),
        major_evidence_gate=MajorEvidenceGateResult(impact_level="informational"),
    )
    cleaned = sanitize_llm_prose("verdict: supports_hypothesis\nExtra prose.", interp)
    assert "supports_hypothesis" not in cleaned or cleaned == "Base conclusion."


def test_api_runs_detail_and_export(client, research_db):
    _index_wf()
    r = client.get("/api/v2/research/runs/wf_test_001/detail")
    assert r.status_code == 200
    body = r.json()
    assert body["interpretation"]["verdict"]

    exp = client.get("/api/v2/research/runs/wf_test_001/export?format=json")
    assert exp.status_code == 200

    notes = client.patch(
        "/api/v2/research/runs/wf_test_001/notes",
        json=ResearchRunNoteRequest(notes="test note").model_dump(),
    )
    assert notes.status_code == 200
    assert notes.json()["research_notes"] == "test note"


def test_api_compare_detail_requires_two(client, research_db):
    _index_wf()
    bad = client.get("/api/v2/research/runs/compare/detail?run_ids=wf_test_001")
    assert bad.status_code == 400
