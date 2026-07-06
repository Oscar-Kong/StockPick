"""Pydantic contracts for Factor Discovery mining sessions."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from engines.factor.discovery.validation_models import FactorValidationConfig
from models.schemas_factor_discovery import DiscoveryPeriodSplit
from services.factor_discovery.llm.models import FactorResearchRequest, NormalizedFactorResearchRequest

MINING_POLICY_VERSION = "factor-mining-v1"
MAX_ADVANCE_STEPS_HARD = 10


class MiningSessionMode(str, Enum):
    DISABLED = "disabled"
    SUPERVISED = "supervised"
    BOUNDED_AUTO = "bounded_auto"


class MiningSessionStatus(str, Enum):
    DRAFT = "DRAFT"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    AUTHORIZED = "AUTHORIZED"
    GENERATING_HYPOTHESES = "GENERATING_HYPOTHESES"
    AWAITING_HYPOTHESIS_REVIEW = "AWAITING_HYPOTHESIS_REVIEW"
    TRANSLATING_FORMULAS = "TRANSLATING_FORMULAS"
    AWAITING_FORMULA_REVIEW = "AWAITING_FORMULA_REVIEW"
    READY_TO_LAUNCH = "READY_TO_LAUNCH"
    RUNNING_EXPERIMENTS = "RUNNING_EXPERIMENTS"
    ANALYZING_RESULTS = "ANALYZING_RESULTS"
    CRITIQUING_RESULTS = "CRITIQUING_RESULTS"
    AWAITING_REVISION_REVIEW = "AWAITING_REVISION_REVIEW"
    PREPARING_REVISIONS = "PREPARING_REVISIONS"
    READY_TO_RELAUNCH = "READY_TO_RELAUNCH"
    PAUSED = "PAUSED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class LineageStatus(str, Enum):
    HYPOTHESIS_PENDING = "HYPOTHESIS_PENDING"
    HYPOTHESIS_REJECTED = "HYPOTHESIS_REJECTED"
    HYPOTHESIS_APPROVED = "HYPOTHESIS_APPROVED"
    FORMULA_PENDING = "FORMULA_PENDING"
    FORMULA_PARSE_FAILED = "FORMULA_PARSE_FAILED"
    FORMULA_COMPILE_FAILED = "FORMULA_COMPILE_FAILED"
    FORMULA_REVIEW_PENDING = "FORMULA_REVIEW_PENDING"
    FORMULA_REJECTED = "FORMULA_REJECTED"
    FORMULA_APPROVED = "FORMULA_APPROVED"
    DEFINITION_CREATED = "DEFINITION_CREATED"
    READY_TO_LAUNCH = "READY_TO_LAUNCH"
    RUN_PENDING = "RUN_PENDING"
    RUNNING = "RUNNING"
    RUN_FAILED = "RUN_FAILED"
    VALIDATION_COMPLETED = "VALIDATION_COMPLETED"
    CRITIQUE_PENDING = "CRITIQUE_PENDING"
    CRITIQUE_COMPLETED = "CRITIQUE_COMPLETED"
    REVISION_PROPOSED = "REVISION_PROPOSED"
    REVISION_REVIEW_PENDING = "REVISION_REVIEW_PENDING"
    REVISION_APPROVED = "REVISION_APPROVED"
    REVISION_REJECTED = "REVISION_REJECTED"
    READY_TO_RELAUNCH = "READY_TO_RELAUNCH"
    STOPPED = "STOPPED"
    PROMISING_FOR_HUMAN_REVIEW = "PROMISING_FOR_HUMAN_REVIEW"
    COMPLETED_AFTER_SESSION_CANCELLATION = "COMPLETED_AFTER_SESSION_CANCELLATION"


class PostValidationAction(str, Enum):
    PAUSE_PROMISING = "PAUSE_PROMISING"
    REQUEST_CRITIQUE = "REQUEST_CRITIQUE"
    PROPOSE_REVISION = "PROPOSE_REVISION"
    STOP_LINEAGE = "STOP_LINEAGE"
    RETRY_INFRASTRUCTURE = "RETRY_INFRASTRUCTURE"
    AWAIT_HUMAN_DECISION = "AWAIT_HUMAN_DECISION"
    COMPLETE_SESSION_IF_IDLE = "COMPLETE_SESSION_IF_IDLE"


class CritiqueRevisionRecommendation(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    NOT_RECOMMENDED = "NOT_RECOMMENDED"
    HUMAN_DECISION_REQUIRED = "HUMAN_DECISION_REQUIRED"


class RunMonitorStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    ARTIFACT_PENDING = "ARTIFACT_PENDING"
    INDEX_PENDING = "INDEX_PENDING"
    COMPLETE = "COMPLETE"


class NearDuplicateAction(str, Enum):
    WARN = "WARN"
    PAUSE = "PAUSE"
    REJECT = "REJECT"


PROMISING_POLICY_VERSION = "promising-candidate-v1"
BOUNDED_REVISION_POLICY_VERSION = "bounded_revision_policy_v1"
FUTILITY_POLICY_VERSION = "futility-v1"
QUEUE_PRIORITY_VERSION = "queue-priority-v1"


class PauseTrigger(str, Enum):
    EVERY_HYPOTHESIS = "EVERY_HYPOTHESIS"
    EVERY_FORMULA = "EVERY_FORMULA"
    BEFORE_EACH_EXPERIMENT = "BEFORE_EACH_EXPERIMENT"
    AFTER_EACH_EXPERIMENT = "AFTER_EACH_EXPERIMENT"
    BEFORE_EACH_REVISION = "BEFORE_EACH_REVISION"
    AFTER_EACH_REVISION_ROUND = "AFTER_EACH_REVISION_ROUND"
    ONLY_ON_POLICY_TRIGGER = "ONLY_ON_POLICY_TRIGGER"


class ContextTier(str, Enum):
    DISCOVERY_ONLY = "DISCOVERY_ONLY"
    DISCOVERY_PLUS_VALIDATION_SUMMARY = "DISCOVERY_PLUS_VALIDATION_SUMMARY"
    FULL_CLOSED_ARTIFACT = "FULL_CLOSED_ARTIFACT"


class FailureCategory(str, Enum):
    DATA_COVERAGE = "DATA_COVERAGE"
    PIT_PROVENANCE = "PIT_PROVENANCE"
    FORMULA_COMPLEXITY = "FORMULA_COMPLEXITY"
    HORIZON_MISMATCH = "HORIZON_MISMATCH"
    WEAK_RANK_IC = "WEAK_RANK_IC"
    UNSTABLE_IC = "UNSTABLE_IC"
    POOR_QUANTILE_MONOTONICITY = "POOR_QUANTILE_MONOTONICITY"
    HIGH_TURNOVER = "HIGH_TURNOVER"
    COST_EROSION = "COST_EROSION"
    HIGH_DRAWDOWN = "HIGH_DRAWDOWN"
    WALK_FORWARD_INSTABILITY = "WALK_FORWARD_INSTABILITY"
    REGIME_DEPENDENCE = "REGIME_DEPENDENCE"
    SECTOR_CONCENTRATION = "SECTOR_CONCENTRATION"
    SIZE_EXPOSURE = "SIZE_EXPOSURE"
    REDUNDANCY = "REDUNDANCY"
    MULTIPLE_TESTING_FAILURE = "MULTIPLE_TESTING_FAILURE"
    INSUFFICIENT_SIGNIFICANCE = "INSUFFICIENT_SIGNIFICANCE"
    INCONCLUSIVE_EVIDENCE = "INCONCLUSIVE_EVIDENCE"


class FactorMiningPausePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    triggers: list[PauseTrigger] = Field(default_factory=list)
    pause_on_promising: bool = True
    pause_on_budget_warning_pct: int = Field(default=80, ge=0, le=100)


class FactorMiningStoppingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    stop_on_budget_exhausted: bool = True
    stop_on_all_lineages_rejected: bool = True
    stop_on_duplicate_only_round: bool = True
    stop_on_no_compilable_formulas: bool = True
    stop_on_max_failures: bool = True
    min_evaluations_for_futility: int = Field(default=1, ge=1)
    min_rank_ic_delta: float = Field(default=0.01, ge=0)
    max_consecutive_deterioration_rounds: int = Field(default=2, ge=1)


class FactorMiningBudgetPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    max_hypothesis_generation_calls: int = Field(default=3, ge=1)
    max_hypotheses: int = Field(default=5, ge=1)
    max_hypotheses_approved_for_translation: int = Field(default=3, ge=1)
    max_formula_candidates_per_hypothesis: int = Field(default=3, ge=1)
    max_total_formula_candidates: int = Field(default=10, ge=1)
    max_formulas_reaching_evaluation: int = Field(default=10, ge=1)
    max_revision_rounds_per_lineage: int = Field(default=2, ge=0)
    max_total_revision_attempts: int = Field(default=6, ge=0)
    max_llm_interactions: int = Field(default=50, ge=1)
    max_input_tokens: int = Field(default=100_000, ge=1)
    max_output_tokens: int = Field(default=50_000, ge=1)
    max_total_tokens: int = Field(default=150_000, ge=1)
    max_provider_retries: int = Field(default=2, ge=0)
    max_failed_attempts: int = Field(default=10, ge=1)
    max_validation_exposures_per_lineage: int = Field(default=2, ge=0)
    max_validation_critiques_per_formula: int = Field(default=1, ge=0)
    max_concurrent_candidates: int = Field(default=3, ge=1)
    max_ast_nodes: int = Field(default=32, ge=1)
    max_formula_depth: int = Field(default=8, ge=1)
    max_lookback: int = Field(default=252, ge=1)
    max_distinct_fields: int = Field(default=8, ge=1)


class FactorMiningAutoPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    auto_accept_executable_hypotheses: bool = False
    auto_approve_formulas: bool = False
    auto_launch_experiments: bool = False
    auto_approve_revisions: bool = False
    auto_compile_definitions: bool = False
    auto_request_critiques: bool = False
    auto_launch_revisions: bool = False
    pause_on_promising: bool = True
    pause_on_safety_warning: bool = True
    pause_on_complexity_increase: bool = True
    pause_on_high_redundancy: bool = True
    pause_before_final_budget_unit: bool = True
    pause_on_inconclusive_evidence: bool = True


class FactorMiningSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    research_family_id: str
    research_request: FactorResearchRequest
    session_mode: MiningSessionMode = MiningSessionMode.SUPERVISED
    period_split: DiscoveryPeriodSplit
    validation_config: FactorValidationConfig
    snapshot_id: str | None = None
    data_provider_id: str = "fixture"
    data_source_policy_id: str = "research_adjusted_daily_v1"
    pause_policy: FactorMiningPausePolicy | None = None
    stopping_policy: FactorMiningStoppingPolicy | None = None
    budget_policy: FactorMiningBudgetPolicy | None = None
    auto_policy: FactorMiningAutoPolicy | None = None
    actor: str = Field(default="api", max_length=128)


class FactorMiningAuthorizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor: str
    reason: str = Field(min_length=1)
    state_version: int


class FactorRevisionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    parent_formula_candidate_id: str
    parent_formula_hash: str
    lineage_id: str
    revision_round: int = Field(ge=0)
    failure_categories_addressed: list[FailureCategory] = Field(default_factory=list)
    revision_rationale: str
    proposed_dsl: str = Field(min_length=1)
    expected_semantic_change: str = ""
    expected_complexity_change: str = ""
    expected_turnover_direction: str = ""
    required_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    performance_unproven: bool = True


class MiningAdvanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    prior_status: str | None = None
    status: str
    state_version: int
    steps_attempted: int = 0
    steps_executed: int = 0
    events: list[str] = Field(default_factory=list)
    paused: bool = False
    pause_reason: str | None = None
    terminal: bool = False
    terminal_reason: str | None = None
    active_lineages: int = 0
    pending_review_count: int = 0
    runs_awaiting_completion: int = 0
    budget_remaining: dict[str, int] = Field(default_factory=dict)
    next_allowed_actions: list[str] = Field(default_factory=list)


class SessionUsageCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypothesis_generation_calls: int = 0
    hypotheses_generated: int = 0
    hypotheses_approved: int = 0
    formulas_generated: int = 0
    formulas_evaluated: int = 0
    revision_rounds: int = 0
    llm_interactions: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    failed_attempts: int = 0
    validation_exposures: int = 0
    duplicates_prevented: int = 0


class FactorMiningSessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = MINING_POLICY_VERSION
    session_id: str
    research_objective: str
    research_family_id: str
    mode: str
    status: str
    budget_used: SessionUsageCounters
    hypotheses_generated: int = 0
    hypotheses_rejected: int = 0
    formulas_generated: int = 0
    parse_failures: int = 0
    compile_failures: int = 0
    exact_duplicates: int = 0
    experiments_launched: int = 0
    statistical_hypotheses_evaluated: int = 0
    validation_exposures: int = 0
    revision_rounds: int = 0
    lineages_stopped: int = 0
    promising_candidates: int = 0
    multiple_testing_family_size: int = 0
    stopping_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    no_sealed_test: bool = True
    no_lifecycle_promotion: bool = True
    session_hash: str = ""
    event_log_hash: str = ""


class PromisingRuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    status: Literal["PASS", "FAIL", "INCONCLUSIVE", "NOT_EVALUATED"]
    actual: float | str | None = None
    threshold: float | str | None = None
    evidence_path: str = ""
    failure_reason: str = ""
    inconclusive_reason: str = ""


class PromisingCandidatePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROMISING_POLICY_VERSION
    require_integrity_pass: bool = True
    require_closed_artifact: bool = True
    min_valid_date_coverage_pct: float = Field(default=0.7, ge=0, le=1)
    min_mean_rank_ic: float = Field(default=0.02)
    require_robust_significance: bool = True
    min_walk_forward_pass_rate: float = Field(default=0.5, ge=0, le=1)
    max_turnover: float = Field(default=2.0, ge=0)
    max_drawdown: float = Field(default=0.5, ge=0)
    max_redundancy: float = Field(default=0.85, ge=0, le=1)
    allow_inconclusive_optional: bool = True


class PromisingEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall: Literal["PROMISING_FOR_HUMAN_REVIEW", "NOT_PROMISING", "INCONCLUSIVE"]
    rules: list[PromisingRuleResult] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)


class MiningPostValidationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lineage_id: str
    evaluation_id: str
    artifact_id: str | None = None
    acceptance_status: str | None = None
    failure_categories: list[FailureCategory] = Field(default_factory=list)
    integrity_ok: bool = True
    robust_significance_ok: bool = False
    multiple_testing_ok: bool = False
    exposure_available: bool = True
    revision_eligible: bool = False
    revision_rounds_remaining: int = 0
    evaluation_budget_remaining: int = 0
    duplicate_risk: bool = False
    redundancy_high: bool = False
    promising_result: PromisingEvaluationResult | None = None
    recommended_action: PostValidationAction
    reason_codes: list[str] = Field(default_factory=list)


class MiningStoppingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_stop: bool = False
    should_pause: bool = False
    session_terminal_status: MiningSessionStatus | None = None
    affected_lineages: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)
    recommended_human_action: str = ""


class SessionActionFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_authorize: bool = False
    can_start: bool = False
    can_advance: bool = False
    can_pause: bool = False
    can_resume: bool = False
    can_cancel: bool = False
    can_approve_hypothesis: bool = False
    can_reject_hypothesis: bool = False
    can_approve_formula: bool = False
    can_reject_formula: bool = False
    can_approve_revision: bool = False
    can_reject_revision: bool = False


class SessionActionDisabledReasons(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_authorize: str | None = None
    can_start: str | None = None
    can_advance: str | None = None
    can_pause: str | None = None
    can_resume: str | None = None
    can_cancel: str | None = None
    can_approve_hypothesis: str | None = None
    can_reject_hypothesis: str | None = None
    can_approve_formula: str | None = None
    can_reject_formula: str | None = None
    can_approve_revision: str | None = None
    can_reject_revision: str | None = None


class AuthorizedSessionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_request: NormalizedFactorResearchRequest
    period_split: DiscoveryPeriodSplit
    validation_config: FactorValidationConfig
    pause_policy: FactorMiningPausePolicy
    stopping_policy: FactorMiningStoppingPolicy
    budget_policy: FactorMiningBudgetPolicy
    auto_policy: FactorMiningAutoPolicy
