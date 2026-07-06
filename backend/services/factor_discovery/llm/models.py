"""Pydantic schemas for Factor Discovery LLM operations."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from models.schemas_factor_discovery import FactorDirection, InputDataClass

LLM_RESPONSE_SCHEMA_VERSION = "factor-llm-v1"


class LlmOperationType(str, Enum):
    REQUEST_NORMALIZE = "REQUEST_NORMALIZE"
    HYPOTHESIS_GENERATE = "HYPOTHESIS_GENERATE"
    HYPOTHESIS_CRITIQUE = "HYPOTHESIS_CRITIQUE"
    FORMULA_TRANSLATE = "FORMULA_TRANSLATE"
    FORMULA_REVIEW = "FORMULA_REVIEW"
    RUN_INTERPRET = "RUN_INTERPRET"


class CandidateType(str, Enum):
    HYPOTHESIS = "HYPOTHESIS"
    FORMULA = "FORMULA"
    CRITIQUE = "CRITIQUE"
    INTERPRETATION = "INTERPRETATION"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class CandidateValidationStatus(str, Enum):
    EXECUTABLE = "EXECUTABLE"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    UNSUPPORTED_DATA = "UNSUPPORTED_DATA"
    INVALID = "INVALID"


class FormulaCompileStatus(str, Enum):
    PARSE_FAILED = "PARSE_FAILED"
    COMPILE_FAILED = "COMPILE_FAILED"
    COMPILED_FOR_REVIEW = "COMPILED_FOR_REVIEW"


class FactorResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_objective: str = Field(min_length=1, max_length=4000)
    intended_universe: str = Field(default="research", max_length=64)
    holding_period_sessions: int | None = Field(default=None, ge=1, le=504)
    rebalance_frequency: str | None = Field(default=None, max_length=32)
    max_turnover_preference: str | None = None
    required_data_classes: list[InputDataClass] = Field(default_factory=list)
    excluded_factor_families: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=5, ge=1, le=5)
    actor: str = Field(default="api", max_length=128)


class NormalizedFactorResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_objective: str
    intended_universe: str
    holding_period_sessions: int
    rebalance_frequency: str
    candidate_count: int
    required_data_classes: list[str]
    primary_horizon_sessions: int
    validation_config_family_id: str = "default_v1"


class GeneratedFactorHypothesisCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_name: str = Field(min_length=1, max_length=128)
    economic_rationale: str = Field(min_length=1)
    expected_mechanism: str = Field(min_length=1)
    expected_direction: FactorDirection
    intended_universe: str
    expected_holding_period_sessions: int = Field(ge=1, le=504)
    rebalance_frequency: str
    required_data_classes: list[str]
    proposed_fields: list[str]
    expected_market_behavior: str
    expected_failure_conditions: list[str] = Field(default_factory=list)
    known_risks: list[str] = Field(default_factory=list)
    potential_benchmark_overlap: str = ""
    expected_turnover_category: str = "medium"
    complexity_category: str = "moderate"
    assumptions: list[str] = Field(default_factory=list)
    data_availability_confidence: str = "medium"
    profitability_unproven: bool = True


class GeneratedFactorHypothesisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    candidates: list[GeneratedFactorHypothesisCandidate] = Field(min_length=1)


class HypothesisCritiqueResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    summary_judgment: str
    economic_plausibility_concerns: list[str] = Field(default_factory=list)
    data_availability_concerns: list[str] = Field(default_factory=list)
    pit_concerns: list[str] = Field(default_factory=list)
    survivorship_concerns: list[str] = Field(default_factory=list)
    expected_redundancy: str = ""
    turnover_concerns: list[str] = Field(default_factory=list)
    horizon_mismatch: str = ""
    regime_dependence: str = ""
    potential_leakage_risk: str = ""
    formula_translation_cautions: list[str] = Field(default_factory=list)
    recommended_decision: Literal["CONTINUE_TO_FORMULA", "REVISE_HYPOTHESIS", "REJECT"]
    questions_for_human: list[str] = Field(default_factory=list)


class GeneratedFactorFormula(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    hypothesis_candidate_id: str
    proposed_factor_name: str
    dsl_version: str = "factor-dsl-v1"
    dsl_source: str = Field(min_length=1)
    expected_direction: FactorDirection
    required_fields: list[str] = Field(default_factory=list)
    formula_explanation: str
    operator_explanation: str = ""
    expected_lookback: str = ""
    expected_data_requirements: list[str] = Field(default_factory=list)
    potential_risks: list[str] = Field(default_factory=list)
    claimed_unsupported_capabilities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class FormulaReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    fidelity_to_hypothesis: str
    economic_interpretability: str
    complexity_concern: str = ""
    data_readiness_concern: str = ""
    pit_concern: str = ""
    expected_turnover_concern: str = ""
    likely_benchmark_overlap: str = ""
    fragility_concern: str = ""
    suggested_decision: Literal["APPROVE_FOR_DEFINITION", "REQUEST_MANUAL_REVISION", "REJECT"]
    explanation: str


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    value: str
    claim: str


class InterpretationRecommendation(str, Enum):
    REJECT = "REJECT"
    KEEP_RESEARCHING = "KEEP_RESEARCHING"
    CONSIDER_PROMISING_REVIEW = "CONSIDER_PROMISING_REVIEW"
    REVALIDATE_MULTIPLE_TESTING_CONTEXT = "REVALIDATE_MULTIPLE_TESTING_CONTEXT"
    REQUEST_SEALED_REVIEW = "REQUEST_SEALED_REVIEW"


class FactorRunInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = LLM_RESPONSE_SCHEMA_VERSION
    plain_language_summary: str
    factor_intent: str
    discovery_assessment: str
    validation_assessment: str
    walk_forward_assessment: str
    cost_turnover_assessment: str
    robustness_assessment: str
    redundancy_assessment: str = ""
    significance_assessment: str
    multiple_testing_assessment: str = ""
    data_quality_assessment: str = ""
    key_failure_reasons: list[str] = Field(default_factory=list)
    key_strengths: list[str] = Field(default_factory=list)
    known_limitations: list[str] = Field(default_factory=list)
    sealed_test_note: str = ""
    recommended_next_action: InterpretationRecommendation
    evidence_references: list[EvidenceReference] = Field(default_factory=list)


class FactorLlmRequestMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_type: LlmOperationType
    actor: str
    research_family_id: str | None = None
    hypothesis_id: str | None = None
    run_id: str | None = None
    idempotency_key: str | None = None
