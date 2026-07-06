"""Supervised mining orchestrator integration tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from services.factor_discovery.llm.client import FixtureLlmClient
from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService
from services.factor_discovery.llm.models import ReviewStatus
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.mining.models import MiningSessionStatus
from services.factor_discovery.mining.orchestrator import FactorMiningOrchestrator
from services.factor_discovery.mining.repositories import FactorMiningLineageRepository, FactorMiningSessionRepository
from services.factor_discovery.mining.session_service import FactorMiningSessionService
from tests.fixtures.factor_discovery.llm.helpers import register_formula_fixture, register_hypothesis_fixture
from tests.fixtures.factor_discovery.mining.helpers import authorize_and_start, enable_mining, mining_session_request


@pytest.fixture
def mining_env(isolated_backend_env, monkeypatch):
    init_quant_db()
    client = enable_mining(monkeypatch)
    return client


def test_supervised_pauses_for_hypothesis_review(mining_env: FixtureLlmClient):
    register_hypothesis_fixture()
    req = mining_session_request()
    session_svc = FactorMiningSessionService()
    created = session_svc.create_session(req)
    authorize_and_start(session_svc, created["session_id"])
    orch = FactorMiningOrchestrator(llm_client=mining_env)
    result = orch.advance(created["session_id"], maximum_steps=1, actor="tester")
    assert result.paused is True
    assert result.pause_reason == "hypothesis_review_required"


def test_supervised_e2e_through_experiment(mining_env: FixtureLlmClient):
    register_hypothesis_fixture()
    req = mining_session_request()
    session_svc = FactorMiningSessionService()
    created = session_svc.create_session(req)
    authorize_and_start(session_svc, created["session_id"])
    orch = FactorMiningOrchestrator(
        llm_client=mining_env,
        formula_service=FactorFormulaTranslationService(llm_client=mining_env),
    )
    sid = created["session_id"]
    orch.advance(sid, actor="tester")
    lineages = FactorMiningLineageRepository().list_for_session(sid)
    hyp_id = lineages[0].origin_hypothesis_candidate_id
    row = FactorMiningSessionRepository().get(sid)
    session_svc.approve_hypothesis(sid, hyp_id, actor="reviewer", reason="ok", state_version=row.state_version)
    register_formula_fixture(hyp_id)
    orch.advance(sid, maximum_steps=2, actor="tester")
    lin = lineages[0]
    lin = FactorMiningLineageRepository().get(lin.lineage_id)
    formula_id = lin.current_formula_candidate_id
    assert formula_id
    row = FactorMiningSessionRepository().get(sid)
    session_svc.approve_formula(sid, formula_id, actor="reviewer", reason="compiled", state_version=row.state_version)
    result = orch.advance(sid, maximum_steps=3, actor="tester")
    assert result.status in {
        MiningSessionStatus.COMPLETED.value,
        MiningSessionStatus.ANALYZING_RESULTS.value,
        MiningSessionStatus.RUNNING_EXPERIMENTS.value,
        MiningSessionStatus.READY_TO_LAUNCH.value,
        MiningSessionStatus.PREPARING_REVISIONS.value,
        MiningSessionStatus.AWAITING_REVISION_REVIEW.value,
        MiningSessionStatus.PAUSED.value,
    }
