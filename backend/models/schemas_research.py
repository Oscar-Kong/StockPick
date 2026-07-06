"""Quant Lab research foundation — ideas, experiments, runs, evidence memory, proposals."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from models.schemas_v2 import QuantLabLastRunSummary

IdeaStatus = Literal[
    "new",
    "saved",
    "ready_to_test",
    "running",
    "supported",
    "rejected",
    "inconclusive",
    "archived",
]

IdeaSourceType = Literal[
    "factor_deterioration",
    "factor_improvement",
    "prediction_drift",
    "recommendation_calibration",
    "market_regime",
    "scan_dispersion",
    "portfolio_concentration",
    "pair_relationship",
    "data_quality",
    "failed_experiment",
    "user_created",
]

ExperimentType = Literal[
    "factor_validation",
    "walk_forward",
    "prediction_calibration",
    "pairs_discovery",
    "similar_signal",
    "portfolio_policy",
    "scan_evaluation",
    "factor_discovery",
]

ResearchRunType = Literal[
    "factor_ic_panel",
    "walk_forward",
    "prediction_outcomes",
    "pairs",
    "similar_signal",
    "portfolio_policy",
    "quant_job",
    "scan_evaluation",
]

RunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]

EvidenceImpact = Literal[
    "informational",
    "supporting",
    "contradicting",
    "major_positive",
    "major_negative",
    "integrity_blocker",
]

ConfirmationStatus = Literal["pending", "confirmed", "contradicted", "expired", "inconclusive"]

ProposalStatus = Literal[
    "draft",
    "needs_validation",
    "ready_for_review",
    "rejected",
    "approved_for_staging",
    "archived",
]

ExperimentPreset = Literal[
    "quick_check",
    "standard_research",
    "robust_validation",
    "scan_eval_smoke",
    "exploratory",
    "robust",
    "custom",
]

UniverseSource = Literal[
    "latest_scan",
    "saved_scan",
    "watchlist",
    "portfolio_holdings",
    "full_bucket",
    "custom_symbols",
]

ExperimentStage = Literal[
    "validating",
    "resolving_universe",
    "loading_prices",
    "calculating_features",
    "running_analysis",
    "calculating_outcomes",
    "evaluating_reliability",
    "persisting_result",
    "preparing_universe",
    "replaying_scans",
    "calculating_forward_outcomes",
    "generating_charts",
    "loading_factor_definition",
    "compiling_factor",
    "resolving_data_snapshot",
    "validating_pit_universe",
    "executing_factor",
    "generating_outcomes",
    "resolving_periods",
    "validating_discovery",
    "validating_holdout",
    "running_walk_forward",
    "evaluating_acceptance",
    "persisting_artifact",
    "indexing_result",
    "complete",
    "failed",
]


class ResearchIdeaCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    hypothesis: str = ""
    description: str = ""
    why_now: str = ""
    source_type: IdeaSourceType = "user_created"
    source_references: list[str] = Field(default_factory=list)
    sleeve: str | None = None
    universe_definition: dict[str, Any] = Field(default_factory=dict)
    suggested_experiment_type: ExperimentType | None = None
    suggested_parameters: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=50, ge=0, le=100)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: IdeaStatus = "new"
    user_notes: str = ""


class ResearchIdeaUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    hypothesis: str | None = None
    description: str | None = None
    why_now: str | None = None
    source_type: IdeaSourceType | None = None
    source_references: list[str] | None = None
    sleeve: str | None = None
    universe_definition: dict[str, Any] | None = None
    suggested_experiment_type: ExperimentType | None = None
    suggested_parameters: dict[str, Any] | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    status: IdeaStatus | None = None
    user_notes: str | None = None


class ResearchIdeaResponse(BaseModel):
    id: str
    title: str
    hypothesis: str
    description: str
    why_now: str
    source_type: IdeaSourceType
    source_references: list[str]
    sleeve: str | None
    universe_definition: dict[str, Any]
    suggested_experiment_type: ExperimentType | None
    suggested_parameters: dict[str, Any]
    priority: int
    confidence: float
    status: IdeaStatus
    user_notes: str
    created_at: datetime
    updated_at: datetime


class ResearchIdeaListResponse(BaseModel):
    ideas: list[ResearchIdeaResponse]
    total: int
    offset: int
    limit: int


class ResearchExperimentCreate(BaseModel):
    idea_id: str | None = None
    name: str = Field(min_length=1, max_length=256)
    experiment_type: ExperimentType
    hypothesis: str = ""
    null_hypothesis: str = ""
    success_criteria: str = ""
    failure_criteria: str = ""
    sleeve: str | None = None
    universe_definition: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    preset: ExperimentPreset | None = None
    notes: str = ""


class ResearchExperimentUpdate(BaseModel):
    idea_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=256)
    experiment_type: ExperimentType | None = None
    hypothesis: str | None = None
    null_hypothesis: str | None = None
    success_criteria: str | None = None
    failure_criteria: str | None = None
    sleeve: str | None = None
    universe_definition: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    preset: ExperimentPreset | None = None
    notes: str | None = None


class ResearchExperimentResponse(BaseModel):
    id: str
    idea_id: str | None
    name: str
    experiment_type: ExperimentType
    hypothesis: str
    null_hypothesis: str
    success_criteria: str
    failure_criteria: str
    sleeve: str | None
    universe_definition: dict[str, Any]
    parameters: dict[str, Any]
    preset: ExperimentPreset | None
    notes: str
    created_at: datetime
    updated_at: datetime


class ResearchExperimentListResponse(BaseModel):
    experiments: list[ResearchExperimentResponse]
    total: int
    offset: int
    limit: int


class ResultReference(BaseModel):
    store: str
    run_id: str
    detail_path: str | None = None


class ResearchRunMetric(BaseModel):
    label: str
    value: str | float | int


ResearchVerdict = Literal[
    "supports_hypothesis",
    "rejects_hypothesis",
    "inconclusive",
    "insufficient_data",
    "invalid",
]


class ResearchRunReliability(BaseModel):
    score: int = Field(ge=0, le=100)
    status: str = "insufficient_data"
    reasons: list[str] = Field(default_factory=list)


class ResearchRunInterpretation(BaseModel):
    verdict: ResearchVerdict
    conclusion: str
    evidence_impact: EvidenceImpact
    reliability: ResearchRunReliability
    supporting_observations: list[str] = Field(default_factory=list, max_length=3)
    main_limitation: str = ""
    suggested_next_action: str = ""
    major_evidence_gate: MajorEvidenceGateResult
    prose: str | None = None


class ResearchRunSummary(BaseModel):
    run_id: str
    experiment_id: str | None = None
    idea_id: str | None = None
    run_type: str
    name: str
    status: RunStatus
    verdict: str | None = None
    evidence_impact: EvidenceImpact = "informational"
    reliability: dict[str, Any] | None = None
    sleeve: str | None = None
    universe: list[str] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    strategy_version: str = ""
    factor_model_version: str = ""
    data_cutoff: str | None = None
    sample_size: int | None = None
    primary_metrics: list[ResearchRunMetric] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_reference: ResultReference


class ResearchRunListItem(ResearchRunSummary):
    duration_seconds: int | None = None
    archived: bool = False
    research_notes: str = ""
    reliability_score: int | None = None


class ResearchRunListResponse(BaseModel):
    runs: list[ResearchRunListItem]
    total: int
    offset: int
    limit: int


class ResearchRunCompareResponse(BaseModel):
    run_ids: list[str]
    comparable: bool
    comparison_notes: list[str] = Field(default_factory=list)
    runs: list[ResearchRunSummary] = Field(default_factory=list)
    shared_sleeve: str | None = None
    shared_run_types: list[str] = Field(default_factory=list)


class EvidenceMemoryCreate(BaseModel):
    symbol: str | None = None
    universe: list[str] | None = None
    original_signal: dict[str, Any] = Field(default_factory=dict)
    factor_snapshot_ref: dict[str, Any] = Field(default_factory=dict)
    market_regime: str | None = None
    experiment_id: str | None = None
    run_id: str | None = None
    deterministic_finding: str = ""
    verdict: str | None = None
    evidence_impact: EvidenceImpact = "informational"
    reliability: dict[str, Any] | None = None
    forward_outcomes: dict[str, Any] = Field(default_factory=dict)
    confirmation_status: ConfirmationStatus = "pending"
    related_decisions: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str | None) -> str | None:
        return v.upper().strip() if v else None


class EvidenceMemoryUpdate(BaseModel):
    symbol: str | None = None
    universe: list[str] | None = None
    original_signal: dict[str, Any] | None = None
    factor_snapshot_ref: dict[str, Any] | None = None
    market_regime: str | None = None
    experiment_id: str | None = None
    run_id: str | None = None
    deterministic_finding: str | None = None
    verdict: str | None = None
    evidence_impact: EvidenceImpact | None = None
    reliability: dict[str, Any] | None = None
    forward_outcomes: dict[str, Any] | None = None
    confirmation_status: ConfirmationStatus | None = None
    related_decisions: list[str] | None = None


class EvidenceMemoryResponse(BaseModel):
    id: int
    symbol: str | None
    universe: list[str] | None
    original_signal: dict[str, Any]
    factor_snapshot_ref: dict[str, Any]
    market_regime: str | None
    experiment_id: str | None
    run_id: str | None
    deterministic_finding: str
    verdict: str | None
    evidence_impact: EvidenceImpact
    reliability: dict[str, Any] | None
    forward_outcomes: dict[str, Any]
    confirmation_status: ConfirmationStatus
    related_decisions: list[str]
    created_at: datetime
    updated_at: datetime


class EvidenceMemoryListResponse(BaseModel):
    items: list[EvidenceMemoryResponse]
    total: int
    offset: int
    limit: int


class FactorLineageResponse(BaseModel):
    id: int
    factor_id: str
    factor_name: str
    raw_factor_version: str
    transformation_version: str
    normalization_method: str
    winsorization_method: str
    neutralization_method: str
    formula_version: str
    calculation_date: str
    data_cutoff: str
    universe: list[str]
    sleeve: str
    strategy_version: str
    factor_model_version: str
    created_at: datetime


class FactorLineageListResponse(BaseModel):
    items: list[FactorLineageResponse]
    total: int


class EvidenceImpactEvaluation(BaseModel):
    impact_level: EvidenceImpact
    score_modifier: float = 0.0
    display_only: bool = True
    explanation_codes: list[str] = Field(default_factory=list)
    review_required: bool = False


class MajorEvidenceGateResult(BaseModel):
    impact_level: EvidenceImpact
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    blocking_checks: list[str] = Field(default_factory=list)
    explanation_codes: list[str] = Field(default_factory=list)
    review_required: bool = False


class ChangeProposalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    finding: str = ""
    supporting_run_ids: list[str] = Field(default_factory=list)
    proposed_change: dict[str, Any] = Field(default_factory=dict)
    affected_sleeve: str | None = None
    affected_factors: list[str] = Field(default_factory=list)
    expected_benefit: str = ""
    main_risks: str = ""
    required_validation: str = ""
    status: ProposalStatus = "draft"


class ChangeProposalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=256)
    finding: str | None = None
    supporting_run_ids: list[str] | None = None
    proposed_change: dict[str, Any] | None = None
    affected_sleeve: str | None = None
    affected_factors: list[str] | None = None
    expected_benefit: str | None = None
    main_risks: str | None = None
    required_validation: str | None = None
    status: ProposalStatus | None = None


class ChangeProposalResponse(BaseModel):
    id: str
    title: str
    finding: str
    supporting_run_ids: list[str]
    proposed_change: dict[str, Any]
    affected_sleeve: str | None
    affected_factors: list[str]
    expected_benefit: str
    main_risks: str
    required_validation: str
    status: ProposalStatus
    created_at: datetime
    updated_at: datetime


class ChangeProposalListResponse(BaseModel):
    proposals: list[ChangeProposalResponse]
    total: int
    offset: int
    limit: int


class ResearchBriefFinding(BaseModel):
    finding_id: str
    title: str
    explanation: str
    supporting_metric: str
    source_reference: str
    why_it_matters: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_impact: EvidenceImpact = "informational"
    suggested_experiment_type: ExperimentType
    suggested_parameters: dict[str, Any] = Field(default_factory=dict)


class ResearchActivityItem(BaseModel):
    id: str
    activity_type: str
    label: str
    occurred_at: str | None = None
    status: str | None = None
    run_id: str | None = None


class EvidenceMaintenanceAction(BaseModel):
    action_id: str
    label: str
    description: str
    endpoint: str
    method: str = "POST"
    available: bool = True
    reason_unavailable: str | None = None


class ResearchOverviewResponse(BaseModel):
    generated_at: str
    sleeve: str
    research_confidence_status: str
    research_confidence_score: int = Field(ge=0, le=100)
    data_freshness: str
    strategy_version: str
    factor_model_version: str
    market_regime: str | None = None
    latest_experiment: ResearchExperimentResponse | None = None
    latest_completed_run: ResearchRunSummary | None = None
    predictions_resolved: int = 0
    predictions_unresolved: int = 0
    failed_or_blocked_jobs: int = 0
    factor_ic: QuantLabLastRunSummary | None = None
    walk_forward: QuantLabLastRunSummary | None = None
    pairs: QuantLabLastRunSummary | None = None
    major_warnings: list[str] = Field(default_factory=list)
    findings: list[ResearchBriefFinding] = Field(default_factory=list)
    recommended_ideas: list[ResearchIdeaResponse] = Field(default_factory=list)
    recent_activity: list[ResearchActivityItem] = Field(default_factory=list)
    maintenance_actions: list[EvidenceMaintenanceAction] = Field(default_factory=list)


class GenerateIdeasRequest(BaseModel):
    sleeve: str | None = None
    from_findings_only: bool = True
    limit: int = Field(default=10, ge=1, le=50)


class GenerateIdeasResponse(BaseModel):
    created: list[ResearchIdeaResponse]
    skipped_duplicates: int = 0
    findings_used: int = 0


class ExperimentTemplateInfo(BaseModel):
    experiment_type: ExperimentType
    title: str
    description: str
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    universe_sources: list[UniverseSource] = Field(default_factory=list)
    supports_presets: bool = True


class ExperimentTemplatesResponse(BaseModel):
    templates: list[ExperimentTemplateInfo]


class PresetParameterValue(BaseModel):
    key: str
    value: str | int | float | bool | list[Any]
    description: str = ""


class ExperimentPresetInfo(BaseModel):
    preset_id: ExperimentPreset
    title: str
    description: str
    major_evidence_eligible: bool = False
    verdict_ceiling: str = "exploratory"
    parameters: list[PresetParameterValue] = Field(default_factory=list)


class ExperimentPresetsResponse(BaseModel):
    presets: list[ExperimentPresetInfo]


class ExperimentValidateRequest(BaseModel):
    experiment_type: ExperimentType
    sleeve: str | None = None
    universe_definition: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    preset: ExperimentPreset | None = None
    hypothesis: str = ""
    null_hypothesis: str = ""
    success_criteria: str = ""
    failure_criteria: str = ""


class ExperimentValidationCheck(BaseModel):
    key: str
    label: str
    value: str | int | float | bool | None = None
    status: Literal["ok", "warning", "error", "missing"] = "ok"
    detail: str = ""


class ExperimentValidationResponse(BaseModel):
    valid: bool
    can_run: bool
    symbol_count: int = 0
    missing_data_rate: float | None = None
    expected_periods: int | None = None
    data_cutoff: str | None = None
    dependency_availability: dict[str, bool] = Field(default_factory=dict)
    major_limitations: list[str] = Field(default_factory=list)
    checks: list[ExperimentValidationCheck] = Field(default_factory=list)
    resolved_universe: list[str] = Field(default_factory=list)
    merged_parameters: dict[str, Any] = Field(default_factory=dict)


class ExperimentStageRecord(BaseModel):
    stage: ExperimentStage
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    message: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExperimentJobResponse(BaseModel):
    job_id: str
    experiment_id: str
    status: RunStatus
    current_stage: ExperimentStage | None = None
    stages: list[ExperimentStageRecord] = Field(default_factory=list)
    run_id: str | None = None
    last_success_run_id: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExperimentLaunchResponse(BaseModel):
    job_id: str
    experiment_id: str
    status: RunStatus = "pending"
    duplicate_blocked: bool = False
    message: str = ""


class ChartSeriesPoint(BaseModel):
    x: str | float | int
    y: float | int | None = None
    label: str | None = None


class ChartSeries(BaseModel):
    chart_id: str
    title: str
    chart_type: Literal["line", "bar", "heatmap", "scatter", "area"]
    x_label: str = ""
    y_label: str = ""
    series: list[dict[str, Any]] = Field(default_factory=list)
    empty_reason: str | None = None


class MetricExplanation(BaseModel):
    metric_key: str
    label: str
    measures: str
    preferred_direction: str
    why_it_matters: str
    limitations: str


class ResearchRunDetailResponse(BaseModel):
    summary: ResearchRunListItem
    interpretation: ResearchRunInterpretation
    experiment: ResearchExperimentResponse | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    charts: list[ChartSeries] = Field(default_factory=list)
    metric_explanations: list[MetricExplanation] = Field(default_factory=list)
    evidence_memory: list[EvidenceMemoryResponse] = Field(default_factory=list)
    related_runs: list[ResearchRunSummary] = Field(default_factory=list)
    related_ideas: list[ResearchIdeaResponse] = Field(default_factory=list)
    skipped_data: list[str] = Field(default_factory=list)


class RunComparisonMetricDiff(BaseModel):
    label: str
    values: dict[str, str | float | int | None]
    comparable: bool = True
    note: str = ""


class ResearchRunCompareDetailResponse(BaseModel):
    run_ids: list[str]
    comparable: bool
    compatibility_checks: list[ExperimentValidationCheck] = Field(default_factory=list)
    comparison_notes: list[str] = Field(default_factory=list)
    parameter_diffs: list[RunComparisonMetricDiff] = Field(default_factory=list)
    metric_diffs: list[RunComparisonMetricDiff] = Field(default_factory=list)
    runs: list[ResearchRunListItem] = Field(default_factory=list)
    conclusion: str = ""
    shared_sleeve: str | None = None
    shared_run_types: list[str] = Field(default_factory=list)
    charts: list[ChartSeries] = Field(default_factory=list)


class ResearchRunNoteRequest(BaseModel):
    notes: str = ""


class ResearchRunArchiveRequest(BaseModel):
    archived: bool = True


class ResearchRunFollowUpIdeaRequest(BaseModel):
    title: str | None = None
    hypothesis: str = ""


class ResearchRunDuplicateExperimentResponse(BaseModel):
    experiment_id: str
    run_id: str


class FactorHealthItem(BaseModel):
    factor_id: str
    display_name: str
    lifecycle: str = "hold"
    production_weight: float | None = None
    recent_ic: float | None = None
    long_term_ic: float | None = None
    sample_size: int | None = None
    drift: float | None = None
    horizon_stability: str = "unknown"
    regime_stability: str = "unknown"
    factor_version: str = ""
    transformation_lineage: str = ""
    last_calculation: str | None = None
    last_reliable_validation_run_id: str | None = None
    supporting_run_ids: list[str] = Field(default_factory=list)


class PredictionHealthSummary(BaseModel):
    resolved_count: int = 0
    unresolved_count: int = 0
    stale_count: int = 0
    coverage_pct: float | None = None
    mean_forecast_error_pct: float | None = None
    recommendation_outcomes: dict[str, int] = Field(default_factory=dict)
    horizon_breakdown: dict[str, Any] = Field(default_factory=dict)
    regime_breakdown: dict[str, Any] = Field(default_factory=dict)
    latest_outcome_job: dict[str, Any] | None = None
    calibration_ready: bool = False


class DataHealthSummary(BaseModel):
    provider_availability: dict[str, bool] = Field(default_factory=dict)
    price_freshness: dict[str, Any] = Field(default_factory=dict)
    missing_stocks: list[str] = Field(default_factory=list)
    stale_stocks: list[str] = Field(default_factory=list)
    reconciliation_issues: list[str] = Field(default_factory=list)
    data_confidence: dict[str, Any] = Field(default_factory=dict)
    excluded_stock_counts: dict[str, int] = Field(default_factory=dict)
    integrity_blockers: list[str] = Field(default_factory=list)


class ResearchJobMonitorItem(BaseModel):
    job_id: str
    job_name: str
    status: str
    stage: str = ""
    duration_seconds: int | None = None
    experiment_id: str | None = None
    run_id: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    retry_blocked: bool = False


class ModelConfigurationSummary(BaseModel):
    strategy_version: str = ""
    factor_model_version: str = ""
    current_regime: str | None = None
    dynamic_weights_enabled: bool = False
    weights_by_sleeve: dict[str, dict[str, float]] = Field(default_factory=dict)
    enabled_research_features: dict[str, bool] = Field(default_factory=dict)
    read_only: bool = True


class ModelMonitorResponse(BaseModel):
    sleeve: str
    factor_health: list[FactorHealthItem] = Field(default_factory=list)
    prediction_health: PredictionHealthSummary = Field(default_factory=PredictionHealthSummary)
    data_health: DataHealthSummary = Field(default_factory=DataHealthSummary)
    research_jobs: list[ResearchJobMonitorItem] = Field(default_factory=list)
    model_configuration: ModelConfigurationSummary = Field(default_factory=ModelConfigurationSummary)


class EvidenceReviewFinding(BaseModel):
    finding_id: str
    source_type: Literal["run", "evidence_memory"]
    title: str
    evidence_impact: EvidenceImpact
    verdict: str | None = None
    sleeve: str | None = None
    symbol: str | None = None
    supporting_run_ids: list[str] = Field(default_factory=list)
    gate: MajorEvidenceGateResult | None = None
    sample_size: int | None = None
    review_required: bool = True
    unresolved_warnings: list[str] = Field(default_factory=list)
    model_versions: dict[str, str] = Field(default_factory=dict)
    review_history: list[dict[str, Any]] = Field(default_factory=list)


class EvidenceReviewListResponse(BaseModel):
    findings: list[EvidenceReviewFinding]
    total: int


class EvidenceReviewActionRequest(BaseModel):
    action: Literal[
        "leave_informational",
        "acknowledge_supporting",
        "create_validation_work",
        "create_change_proposal",
        "reject",
        "approve_for_staging",
    ]
    notes: str = ""
    proposal_title: str | None = None


class EvidenceReviewActionResponse(BaseModel):
    finding_id: str
    action: str
    evidence_impact: EvidenceImpact
    proposal_id: str | None = None
    audit_id: int | None = None


class JobRetryResponse(BaseModel):
    job_id: str
    retried_as: str | None = None
    duplicate_blocked: bool = False
    message: str = ""

