"""Formula translation, review, and definition creation tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines.quant_db import init_quant_db
from models.schemas_factor_discovery import FactorLifecycleStatus
from services.factor_discovery.llm.client import set_fixture_response
from services.factor_discovery.llm.formula_review_service import FactorFormulaReviewService
from services.factor_discovery.llm.formula_translation_service import FactorFormulaTranslationService
from services.factor_discovery.llm.hypothesis_service import FactorHypothesisGenerationService
from services.factor_discovery.llm.models import GeneratedFactorFormula, LlmOperationType
from services.factor_discovery.llm.review_service import FactorLlmReviewService
from services.factor_discovery.repositories import FactorDefinitionRepository
from tests.fixtures.factor_discovery.llm.helpers import (
    create_research_family,
    enable_llm_fixture,
    register_formula_fixture,
    register_formula_review_fixture,
    register_hypothesis_fixture,
    sample_research_request,
)


@pytest.fixture
def llm_env(isolated_backend_env, monkeypatch):
    init_quant_db()
    return enable_llm_fixture(monkeypatch)


def _approved_hypothesis(llm_env, family_id):
    register_hypothesis_fixture()
    hyp_id = FactorHypothesisGenerationService(llm_client=llm_env).generate(
        sample_research_request(), research_family_id=family_id
    )["candidate_ids"][0]
    FactorLlmReviewService().approve_hypothesis(hyp_id, actor="reviewer", reason="ok")
    return hyp_id


def test_valid_dsl_compiles_for_review(llm_env):
    family_id = create_research_family()
    hyp_id = _approved_hypothesis(llm_env, family_id)
    register_formula_fixture(hyp_id)
    out = FactorFormulaTranslationService(llm_client=llm_env).translate(hyp_id)
    assert out["compile_status"] == "COMPILED_FOR_REVIEW"


def test_python_injection_parse_failed(llm_env):
    family_id = create_research_family()
    hyp_id = _approved_hypothesis(llm_env, family_id)
    register_formula_fixture(hyp_id, dsl_source='eval("__import__(\'os\')")')
    out = FactorFormulaTranslationService(llm_client=llm_env).translate(hyp_id)
    assert out["compile_status"] == "PARSE_FAILED"


def test_unknown_field_compile_failed(llm_env):
    family_id = create_research_family()
    hyp_id = _approved_hypothesis(llm_env, family_id)
    register_formula_fixture(hyp_id, dsl_source="rank(not_a_real_field)")
    out = FactorFormulaTranslationService(llm_client=llm_env).translate(hyp_id)
    assert out["compile_status"] == "COMPILE_FAILED"


def test_human_approval_creates_draft_definition(llm_env):
    family_id = create_research_family()
    hyp_id = _approved_hypothesis(llm_env, family_id)
    register_formula_fixture(hyp_id)
    formula_id = FactorFormulaTranslationService(llm_client=llm_env).translate(hyp_id)["formula_candidate_id"]
    register_formula_review_fixture()
    FactorFormulaReviewService(llm_client=llm_env).review(formula_id, actor="reviewer")
    from services.factor_discovery.llm.definition_service import FactorDefinitionFromLlmService

    FactorLlmReviewService().approve_formula(formula_id, actor="reviewer", reason="compiled ok")
    created = FactorDefinitionFromLlmService().create_definition(
        formula_id, factor_id="llm_momentum", version="1.0.0", actor="reviewer", reason="approved"
    )
    assert created["lifecycle_status"] == FactorLifecycleStatus.DRAFT.value
    row = FactorDefinitionRepository().get("llm_momentum", "1.0.0")
    assert row is not None
    assert row.lifecycle_status == FactorLifecycleStatus.DRAFT.value


def test_no_experiment_runner_import_in_llm_services():
    import services.factor_discovery.llm.hypothesis_service as hs
    import services.factor_discovery.llm.formula_translation_service as fts
    import services.factor_discovery.llm.interpretation_service as isvc

    for mod in (hs, fts, isvc):
        src = open(mod.__file__, encoding="utf-8").read()
        assert "FactorDiscoveryExperimentRunner" not in src
        assert "experiment_runner" not in src
