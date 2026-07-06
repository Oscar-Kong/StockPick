"""Factor promotion governance contracts — advisory review workflow only."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PROMOTION_SCHEMA_VERSION = "factor-promotion-v1"


class FactorPromotionStatus(str, Enum):
    EXPERIMENTAL = "experimental"
    STAGED = "staged"
    PROMOTION_CANDIDATE = "promotion_candidate"
    SHADOW = "shadow"
    APPROVED_FOR_MANUAL_INTEGRATION = "approved_for_manual_integration"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class PromotionGateVerdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"
    WARNING = "warning"


class PromotionGateResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gate_id: str
    display_name: str
    verdict: PromotionGateVerdict
    threshold: str | None = None
    observed: str | None = None
    explanation: str = ""
    blocking: bool = False


class PromotionGateEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_version: str
    evaluated_at: datetime
    overall_pass: bool
    blocking_failures: list[str] = Field(default_factory=list)
    gates: list[PromotionGateResult] = Field(default_factory=list)


class FactorPromotionCandidateSummary(BaseModel):
    candidate_id: str
    factor_id: str
    factor_version: str
    display_name: str
    sleeve: str
    status: FactorPromotionStatus
    expected_direction: str
    source_staging_run_id: str | None = None
    source_experiment_ids: list[str] = Field(default_factory=list)
    evidence_bundle_hash: str | None = None
    gate_overall_pass: bool | None = None
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    advisory_only: bool = True
    affects_live_ranking: bool = False


class FactorPromotionCandidateDetail(FactorPromotionCandidateSummary):
    description: str = ""
    formula_reference: str = ""
    required_data: list[str] = Field(default_factory=list)
    data_latency_class: str = "daily"
    coverage_statistics: dict[str, Any] = Field(default_factory=dict)
    performance_metrics: dict[str, Any] = Field(default_factory=dict)
    robustness_summary: dict[str, Any] = Field(default_factory=dict)
    transaction_cost_sensitivity: dict[str, Any] = Field(default_factory=dict)
    known_weaknesses: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    status_reason: str = ""
    latest_gate_evaluation: PromotionGateEvaluation | None = None
    change_proposal_id: str | None = None


class FactorPromotionCandidateListResponse(BaseModel):
    items: list[FactorPromotionCandidateSummary]
    total: int
    offset: int
    limit: int


class CreatePromotionCandidateRequest(BaseModel):
    factor_id: str
    factor_version: str
    sleeve: str
    source_staging_run_id: str | None = None
    source_experiment_ids: list[str] = Field(default_factory=list)
    actor: str = "system"
    reason: str = "created_from_staging"


class PromotionStatusTransitionRequest(BaseModel):
    target_status: FactorPromotionStatus
    actor: str
    reason: str = Field(min_length=1, max_length=2000)
    expected_evidence_bundle_hash: str | None = None
    rejection_category: str | None = None


class PromotionStatusTransitionResponse(BaseModel):
    candidate_id: str
    previous_status: FactorPromotionStatus
    new_status: FactorPromotionStatus
    event_id: str
    audit_id: int | None = None


class PromotionAuditEvent(BaseModel):
    event_id: str
    candidate_id: str
    previous_status: str | None
    new_status: str
    actor: str
    reason: str
    approval_source: str | None = None
    created_at: datetime


class PromotionAuditHistoryResponse(BaseModel):
    candidate_id: str
    events: list[PromotionAuditEvent]


class EvidenceBundleSummary(BaseModel):
    bundle_id: str
    candidate_id: str
    bundle_hash: str
    schema_version: str
    generated_at: datetime
    immutable: bool = True
    summary: str = ""
    gate_evaluation: PromotionGateEvaluation | None = None


class EvidenceBundleDetail(EvidenceBundleSummary):
    factor_definition: dict[str, Any] = Field(default_factory=dict)
    staging_manifest: dict[str, Any] = Field(default_factory=dict)
    experiment_runs: list[dict[str, Any]] = Field(default_factory=list)
    baseline_comparison: dict[str, Any] = Field(default_factory=dict)
    regime_results: list[dict[str, Any]] = Field(default_factory=list)
    sleeve_results: list[dict[str, Any]] = Field(default_factory=list)
    quantile_results: dict[str, Any] = Field(default_factory=dict)
    turnover_and_cost: dict[str, Any] = Field(default_factory=dict)
    failure_modes: list[str] = Field(default_factory=list)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    negative_controls: list[dict[str, Any]] = Field(default_factory=list)
    source_artifact_hashes: dict[str, str] = Field(default_factory=dict)
    llm_summary: str | None = None
    llm_summary_disclaimer: str = (
        "LLM summary explains structured evidence only; it does not approve factors or override gates."
    )


class ShadowEvaluationRequest(BaseModel):
    as_of_date: str
    symbols: list[str] = Field(default_factory=list, max_length=50)
    shadow_weight: float = Field(default=0.05, ge=0.0, le=0.25)
    actor: str = "system"


class ShadowSymbolObservation(BaseModel):
    symbol: str
    live_rank: int | None = None
    shadow_rank: int | None = None
    rank_change: int | None = None
    live_score: float
    shadow_score: float
    score_change: float
    candidate_contribution: float
    candidate_coverage: float | None = None
    missing_data_fallback: str | None = None


class ShadowEvaluationRunResponse(BaseModel):
    run_id: str
    candidate_id: str
    sleeve: str
    as_of_date: str
    status: Literal["succeeded", "failed", "blocked"]
    configuration_version: str
    shadow_weight: float
    observations: list[ShadowSymbolObservation] = Field(default_factory=list)
    disagreement_rate: float | None = None
    top_n_membership_changes: int | None = None
    concentration_change: dict[str, Any] = Field(default_factory=dict)
    live_scores_preserved: bool = True
    live_rankings_preserved: bool = True
    created_at: datetime
    error_summary: str | None = None


class ShadowEvaluationListResponse(BaseModel):
    candidate_id: str
    runs: list[ShadowEvaluationRunResponse]
    total: int


class PromotionExplainRequest(BaseModel):
    """Optional LLM narrative — must not alter gates or status."""

    actor: str = "system"


class PromotionExplainResponse(BaseModel):
    candidate_id: str
    summary: str
    disclaimer: str
    gates_unchanged: bool = True
    status_unchanged: bool = True


class PromotionReadinessResponse(BaseModel):
    schema_version: str = PROMOTION_SCHEMA_VERSION
    governance_enabled: bool
    shadow_scoring_enabled: bool
    live_config_mutated: bool = False
    advisory_only: bool = True
