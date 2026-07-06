"""Shared helpers for Factor Discovery LLM tests."""
from __future__ import annotations

import config
from models.schemas_factor_discovery import FactorDirection, InputDataClass
from services.factor_discovery.llm.client import FixtureLlmClient, clear_fixture_responses, set_fixture_response
from services.factor_discovery.llm.models import (
    EvidenceReference,
    FactorResearchRequest,
    FactorRunInterpretation,
    FormulaReviewResult,
    GeneratedFactorFormula,
    GeneratedFactorHypothesisBatch,
    GeneratedFactorHypothesisCandidate,
    HypothesisCritiqueResult,
    InterpretationRecommendation,
    LlmOperationType,
)
from services.factor_discovery.repositories import FactorResearchFamilyRepository


def enable_llm_fixture(monkeypatch) -> FixtureLlmClient:
    import config

    monkeypatch.setenv("FACTOR_DISCOVERY_LLM_ENABLED", "true")
    monkeypatch.setenv("FACTOR_DISCOVERY_LLM_PROVIDER", "fixture")
    config.FACTOR_DISCOVERY_LLM_ENABLED.set(True)
    monkeypatch.setattr(config, "FACTOR_DISCOVERY_LLM_PROVIDER", "fixture", raising=False)
    clear_fixture_responses()
    return FixtureLlmClient()


def create_research_family(*, objective: str = "momentum research") -> str:
    return FactorResearchFamilyRepository().create(
        research_objective=objective,
        intended_universe="research",
        primary_horizon_sessions=21,
        data_source_policy_id="research_adjusted_daily_v1",
        validation_config_family_id="default_v1",
        created_by="test",
    )


def sample_hypothesis_candidate(**overrides) -> GeneratedFactorHypothesisCandidate:
    base = dict(
        candidate_name="Price Momentum Rank",
        economic_rationale="Recent winners may continue outperforming over the next month.",
        expected_mechanism="Attention and trend persistence among retail traders.",
        expected_direction=FactorDirection.HIGHER_IS_BETTER,
        intended_universe="research",
        expected_holding_period_sessions=21,
        rebalance_frequency="monthly",
        required_data_classes=["PRICE"],
        proposed_fields=["return_126d"],
        expected_market_behavior="Winners outperform in calm regimes.",
        expected_failure_conditions=["sharp reversals", "liquidity shocks"],
        known_risks=["crowding", "turnover"],
        profitability_unproven=True,
    )
    base.update(overrides)
    return GeneratedFactorHypothesisCandidate(**base)


def sample_hypothesis_batch(count: int = 1, **overrides) -> GeneratedFactorHypothesisBatch:
    candidates = [sample_hypothesis_candidate(**overrides)]
    if count > 1:
        for i in range(1, count):
            candidates.append(
                sample_hypothesis_candidate(candidate_name=f"Candidate {i + 1}", proposed_fields=["return_21d"])
            )
    return GeneratedFactorHypothesisBatch(candidates=candidates)


def register_hypothesis_fixture(batch: GeneratedFactorHypothesisBatch | None = None) -> None:
    set_fixture_response(LlmOperationType.HYPOTHESIS_GENERATE.value, batch or sample_hypothesis_batch())


def register_critique_fixture() -> None:
    set_fixture_response(
        LlmOperationType.HYPOTHESIS_CRITIQUE.value,
        HypothesisCritiqueResult(
            summary_judgment="Plausible but crowded.",
            recommended_decision="CONTINUE_TO_FORMULA",
            questions_for_human=["Is turnover acceptable?"],
        ),
    )


def register_formula_fixture(
    hypothesis_candidate_id: str,
    *,
    dsl_source: str = "rank(return_126d)",
) -> None:
    set_fixture_response(
        LlmOperationType.FORMULA_TRANSLATE.value,
        GeneratedFactorFormula(
            hypothesis_candidate_id=hypothesis_candidate_id,
            proposed_factor_name="momentum_rank",
            dsl_source=dsl_source,
            expected_direction=FactorDirection.HIGHER_IS_BETTER,
            required_fields=["return_126d"],
            formula_explanation="Cross-sectional rank of 126-day return.",
        ),
    )


def register_formula_review_fixture() -> None:
    set_fixture_response(
        LlmOperationType.FORMULA_REVIEW.value,
        FormulaReviewResult(
            fidelity_to_hypothesis="High",
            economic_interpretability="Clear momentum proxy.",
            suggested_decision="APPROVE_FOR_DEFINITION",
            explanation="Simple rank expression matches hypothesis.",
        ),
    )


def register_interpretation_fixture(*, evidence: list[EvidenceReference]) -> None:
    set_fixture_response(
        LlmOperationType.RUN_INTERPRET.value,
        FactorRunInterpretation(
            plain_language_summary="Mixed validation evidence; sealed test remains closed.",
            factor_intent="Momentum continuation.",
            discovery_assessment="Moderate rank IC in discovery.",
            validation_assessment="Validation IC weaker than discovery.",
            walk_forward_assessment="Some folds pass.",
            cost_turnover_assessment="Turnover elevated.",
            robustness_assessment="Stable across slices.",
            significance_assessment="Primary p-value borderline.",
            sealed_test_note="Sealed metrics not opened.",
            recommended_next_action=InterpretationRecommendation.KEEP_RESEARCHING,
            evidence_references=evidence,
        ),
    )


def sample_research_request(**overrides) -> FactorResearchRequest:
    base = dict(
        research_objective="Find a price momentum factor for research universe.",
        intended_universe="research",
        candidate_count=1,
        actor="tester",
    )
    base.update(overrides)
    return FactorResearchRequest(**base)
