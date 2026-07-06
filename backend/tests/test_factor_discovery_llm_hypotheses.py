"""Hypothesis generation, critique, and review tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_factor_discovery import FactorDirection
from services.factor_discovery.llm.errors import FactorLlmReviewConflictError
from services.factor_discovery.llm.hypothesis_critic_service import FactorHypothesisCriticService
from services.factor_discovery.llm.hypothesis_service import FactorHypothesisGenerationService
from services.factor_discovery.llm.models import (
    CandidateValidationStatus,
    GeneratedFactorHypothesisBatch,
    ReviewStatus,
)
from services.factor_discovery.llm.review_service import FactorLlmReviewService
from services.factor_discovery.llm.validators import validate_hypothesis_candidate
from tests.fixtures.factor_discovery.llm.helpers import (
    create_research_family,
    enable_llm_fixture,
    register_critique_fixture,
    register_hypothesis_fixture,
    sample_hypothesis_batch,
    sample_hypothesis_candidate,
    sample_research_request,
)


@pytest.fixture
def llm_env(isolated_backend_env, monkeypatch):
    init_quant_db()
    client = enable_llm_fixture(monkeypatch)
    return client


def test_valid_hypothesis_batch_persisted(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    svc = FactorHypothesisGenerationService(llm_client=llm_env)
    result = svc.generate(sample_research_request(), research_family_id=family_id)
    assert result["status"] == "completed"
    assert len(result["candidate_ids"]) == 1


def test_unsupported_field_marked_invalid(llm_env):
    cand = sample_hypothesis_candidate(proposed_fields=["forward_return_21d"])
    status = validate_hypothesis_candidate(cand)
    assert status == CandidateValidationStatus.INVALID


def test_critique_does_not_change_review_status(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    gen = FactorHypothesisGenerationService(llm_client=llm_env)
    out = gen.generate(sample_research_request(), research_family_id=family_id)
    hyp_id = out["candidate_ids"][0]
    register_critique_fixture()
    FactorHypothesisCriticService(llm_client=llm_env).critique(hyp_id, actor="tester")
    from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository

    row = FactorLlmCandidateRepository().get(hyp_id)
    assert row.review_status == ReviewStatus.PENDING_REVIEW.value


def test_explicit_hypothesis_approval(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    gen = FactorHypothesisGenerationService(llm_client=llm_env)
    hyp_id = gen.generate(sample_research_request(), research_family_id=family_id)["candidate_ids"][0]
    FactorLlmReviewService().approve_hypothesis(hyp_id, actor="reviewer", reason="economically plausible")
    from services.factor_discovery.llm.candidate_repository import FactorLlmCandidateRepository

    assert FactorLlmCandidateRepository().get(hyp_id).review_status == ReviewStatus.APPROVED.value


def test_rejected_hypothesis_cannot_translate(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    gen = FactorHypothesisGenerationService(llm_client=llm_env)
    hyp_id = gen.generate(sample_research_request(), research_family_id=family_id)["candidate_ids"][0]
    FactorLlmReviewService().reject_hypothesis(hyp_id, actor="reviewer", reason="too crowded")
    from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService

    with pytest.raises(FactorLlmReviewConflictError):
        FactorFormulaTranslationService(llm_client=llm_env).translate(hyp_id)


def test_approval_requires_actor_and_reason(llm_env):
    family_id = create_research_family()
    register_hypothesis_fixture()
    hyp_id = FactorHypothesisGenerationService(llm_client=llm_env).generate(
        sample_research_request(), research_family_id=family_id
    )["candidate_ids"][0]
    with pytest.raises(FactorLlmReviewConflictError):
        FactorLlmReviewService().approve_hypothesis(hyp_id, actor="llm", reason="auto")
    with pytest.raises(FactorLlmReviewConflictError):
        FactorLlmReviewService().approve_hypothesis(hyp_id, actor="reviewer", reason="")
