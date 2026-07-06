"""Persistence and budget tests for Factor Discovery LLM."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from data.db_engine import get_engine
from engines.factor_discovery_models import FactorLlmCandidate, FactorLlmInteraction, FactorLlmReviewEvent
from engines.quant_db import init_quant_db
from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository
from services.factor_discovery.llm.errors import FactorLlmBudgetExceededError
from services.factor_discovery.llm.hypothesis_service import FactorHypothesisGenerationService
from services.factor_discovery.llm.interaction_repository import FactorLlmInteractionRepository
from services.factor_discovery.llm.review_service import FactorLlmReviewService
from sqlalchemy.orm import Session
from tests.fixtures.factor_discovery.llm.helpers import (
    create_research_family,
    enable_llm_fixture,
    register_hypothesis_fixture,
    sample_research_request,
)


@pytest.fixture
def llm_env(isolated_backend_env, monkeypatch):
    init_quant_db()
    return enable_llm_fixture(monkeypatch)


def test_llm_tables_created(isolated_backend_env):
    init_quant_db()
    engine = get_engine()
    with Session(engine) as session:
        assert session.query(FactorLlmInteraction).count() == 0
        assert session.query(FactorLlmCandidate).count() == 0
        assert session.query(FactorLlmReviewEvent).count() == 0


def test_interaction_persisted_without_api_key(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    iid = FactorHypothesisGenerationService(llm_client=llm_env).generate(
        sample_research_request(), research_family_id=family_id, idempotency_key="idem-1"
    )["interaction_id"]
    row = FactorLlmInteractionRepository().get(iid)
    assert row is not None
    assert row.system_prompt_hash
    assert "api_key" not in (row.error_summary or "").lower()


def test_review_event_append_only(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    hyp_id = FactorHypothesisGenerationService(llm_client=llm_env).generate(
        sample_research_request(), research_family_id=family_id
    )["candidate_ids"][0]
    FactorLlmReviewService().approve_hypothesis(hyp_id, actor="reviewer", reason="ok")
    with Session(get_engine()) as session:
        events = session.query(FactorLlmReviewEvent).filter(FactorLlmReviewEvent.candidate_id == hyp_id).all()
    assert len(events) == 1
    assert events[0].new_status == "APPROVED"


def test_daily_family_budget(monkeypatch, llm_env):
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LLM_DAILY_CALLS_PER_FAMILY", 1, raising=False)
    family_id = create_research_family()
    register_hypothesis_fixture()
    svc = FactorHypothesisGenerationService(llm_client=llm_env)
    svc.generate(sample_research_request(), research_family_id=family_id)
    with pytest.raises(FactorLlmBudgetExceededError):
        svc.generate(sample_research_request(), research_family_id=family_id)


def test_idempotent_duplicate_request(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    svc = FactorHypothesisGenerationService(llm_client=llm_env)
    first = svc.generate(sample_research_request(), research_family_id=family_id, idempotency_key="dup-key")
    second = svc.generate(sample_research_request(), research_family_id=family_id, idempotency_key="dup-key")
    assert second.get("duplicate") is True
    assert first["interaction_id"] == second["interaction_id"]
