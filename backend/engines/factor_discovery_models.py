"""SQLAlchemy persistence models for Factor Discovery Phase 5."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, UniqueConstraint

from engines.quant_models import QuantBase


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class FactorHypothesisRecord(QuantBase):
    __tablename__ = "factor_hypothesis_records"

    hypothesis_id = Column(String(64), primary_key=True)
    research_family_id = Column(String(64), nullable=True, index=True)
    name = Column(String(256), nullable=False)
    economic_rationale = Column(Text, nullable=False)
    expected_mechanism = Column(Text, nullable=False)
    expected_direction = Column(String(32), nullable=False)
    intended_universe = Column(String(64), nullable=False)
    holding_period_sessions = Column(Integer, nullable=False)
    rebalance_frequency = Column(String(32), nullable=False)
    required_data_classes_json = Column(Text, nullable=False, default="[]")
    known_risks_json = Column(Text, nullable=False, default="[]")
    expected_failure_conditions_json = Column(Text, nullable=False, default="[]")
    tags_json = Column(Text, nullable=False, default="[]")
    creation_source = Column(String(32), nullable=False, default="user")
    schema_version = Column(String(32), nullable=False, default="factor-discovery-v1")
    created_by = Column(String(128), nullable=False, default="system")
    archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorResearchFamily(QuantBase):
    __tablename__ = "factor_research_families"

    family_id = Column(String(64), primary_key=True)
    research_objective = Column(Text, nullable=False)
    intended_universe = Column(String(64), nullable=False)
    primary_horizon_sessions = Column(Integer, nullable=False)
    data_source_policy_id = Column(String(64), nullable=False)
    validation_config_family_id = Column(String(64), nullable=False)
    attempt_count_policy_version = Column(String(64), nullable=False, default="distinct_formula_evaluations_v1")
    created_by = Column(String(128), nullable=False, default="system")
    closed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorDefinitionRecord(QuantBase):
    __tablename__ = "factor_definition_records"
    __table_args__ = (UniqueConstraint("factor_id", "version", name="uq_factor_definition_version"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    factor_id = Column(String(64), nullable=False, index=True)
    version = Column(String(32), nullable=False)
    hypothesis_id = Column(String(64), nullable=True, index=True)
    parent_factor_id = Column(String(64), nullable=True)
    parent_version = Column(String(32), nullable=True)
    display_name = Column(String(128), nullable=False)
    original_dsl = Column(Text, nullable=False)
    canonical_dsl = Column(Text, nullable=False)
    canonical_ast_json = Column(Text, nullable=False)
    formula_hash = Column(String(80), nullable=False, index=True)
    definition_identity_hash = Column(String(80), nullable=False)
    expected_direction = Column(String(32), nullable=False)
    required_fields_json = Column(Text, nullable=False, default="[]")
    data_source_policy_id = Column(String(64), nullable=False)
    holding_period_sessions = Column(Integer, nullable=False)
    rebalance_frequency = Column(String(32), nullable=False)
    missing_value_policy = Column(String(64), nullable=False)
    outlier_policy = Column(String(64), nullable=False)
    neutralization_keys_json = Column(Text, nullable=False, default="[]")
    schema_version = Column(String(32), nullable=False, default="factor-discovery-v1")
    lifecycle_status = Column(String(32), nullable=False, default="DRAFT")
    lifecycle_version = Column(Integer, nullable=False, default=0)
    recommended_status = Column(String(32), nullable=True)
    created_by = Column(String(128), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorResearchDataSnapshot(QuantBase):
    __tablename__ = "factor_research_data_snapshots"

    snapshot_id = Column(String(64), primary_key=True)
    provider_id = Column(String(64), nullable=False)
    data_source_policy_id = Column(String(64), nullable=False)
    universe_source = Column(String(64), nullable=False)
    universe_version = Column(String(64), nullable=False)
    universe_pit_evidence_json = Column(Text, nullable=False, default="{}")
    panel_hash = Column(String(80), nullable=False)
    canonical_session_hash = Column(String(80), nullable=False)
    field_list_json = Column(Text, nullable=False, default="[]")
    field_provenance_summary_json = Column(Text, nullable=False, default="{}")
    adjustment_status = Column(String(32), nullable=False)
    start_session = Column(String(10), nullable=False)
    end_session = Column(String(10), nullable=False)
    row_count = Column(Integer, nullable=False)
    symbol_count = Column(Integer, nullable=False)
    date_count = Column(Integer, nullable=False)
    storage_reference = Column(Text, nullable=True)
    storage_format = Column(String(32), nullable=False, default="fixture_json_v1")
    artifact_present = Column(Boolean, nullable=False, default=False)
    snapshot_identity_hash = Column(String(80), nullable=True, index=True)
    provider_data_version = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorDiscoveryRun(QuantBase):
    __tablename__ = "factor_discovery_runs"

    run_id = Column(String(64), primary_key=True)
    experiment_id = Column(String(64), nullable=True, index=True)
    job_id = Column(String(64), nullable=True, index=True)
    factor_id = Column(String(64), nullable=False, index=True)
    factor_version = Column(String(32), nullable=False)
    research_family_id = Column(String(64), nullable=False, index=True)
    run_type = Column(String(32), nullable=False, default="factor_discovery")
    status = Column(String(32), nullable=False, default="pending")
    current_stage = Column(String(64), nullable=True)
    panel_snapshot_id = Column(String(64), nullable=True)
    period_split_json = Column(Text, nullable=False, default="{}")
    validation_config_json = Column(Text, nullable=False, default="{}")
    formula_hash = Column(String(80), nullable=True)
    plan_hash = Column(String(80), nullable=True)
    panel_hash = Column(String(80), nullable=True)
    canonical_session_hash = Column(String(80), nullable=True)
    execution_hash = Column(String(80), nullable=True)
    closed_artifact_hash = Column(String(80), nullable=True)
    opened_artifact_hash = Column(String(80), nullable=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    launch_payload_hash = Column(String(80), nullable=True)
    recommended_status = Column(String(32), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_stage = Column(String(64), nullable=True)
    error_summary = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=False, default="system")
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorDiscoveryAttempt(QuantBase):
    __tablename__ = "factor_discovery_attempts"

    attempt_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    research_family_id = Column(String(64), nullable=False, index=True)
    factor_id = Column(String(64), nullable=False)
    factor_version = Column(String(32), nullable=False)
    formula_hash = Column(String(80), nullable=True)
    attempt_kind = Column(String(32), nullable=False)
    attempt_sequence = Column(Integer, nullable=False)
    stage_reached = Column(String(64), nullable=True)
    outcome = Column(String(64), nullable=False)
    error_code = Column(String(64), nullable=True)
    error_summary = Column(Text, nullable=True)
    metric_evaluation_started = Column(Boolean, nullable=False, default=False)
    primary_horizon_sessions = Column(Integer, nullable=True)
    validation_config_hash = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorValidationArtifactRecord(QuantBase):
    __tablename__ = "factor_validation_artifact_records"
    __table_args__ = (UniqueConstraint("validation_artifact_hash", name="uq_factor_validation_artifact_hash"),)

    artifact_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    open_state = Column(String(32), nullable=False, default="CLOSED")
    closed_artifact_id = Column(String(64), nullable=True, index=True)
    artifact_schema_version = Column(String(64), nullable=False)
    validation_engine_version = Column(String(64), nullable=False)
    artifact_json = Column(Text, nullable=False)
    formula_hash = Column(String(80), nullable=False)
    plan_hash = Column(String(80), nullable=False)
    panel_hash = Column(String(80), nullable=False)
    canonical_session_hash = Column(String(80), nullable=False)
    execution_hash = Column(String(80), nullable=False)
    outcome_hashes_json = Column(Text, nullable=False, default="{}")
    period_hash = Column(String(80), nullable=False)
    validation_config_hash = Column(String(80), nullable=False)
    validation_artifact_hash = Column(String(80), nullable=False)
    acceptance_status = Column(String(32), nullable=False)
    multiple_testing_method = Column(String(32), nullable=False)
    declared_family_size = Column(Integer, nullable=True)
    derived_family_size = Column(Integer, nullable=True)
    family_size_at_evaluation = Column(Integer, nullable=True)
    prior_artifact_id = Column(String(64), nullable=True, index=True)
    revalidation_of_artifact_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorSealedTestReceipt(QuantBase):
    __tablename__ = "factor_sealed_test_receipts"
    __table_args__ = (
        UniqueConstraint(
            "factor_id",
            "factor_version",
            "formula_hash",
            "plan_hash",
            "panel_snapshot_id",
            "period_hash",
            "validation_config_hash",
            "access_policy_version",
            name="uq_factor_sealed_test_identity",
        ),
    )

    receipt_id = Column(String(64), primary_key=True)
    run_id = Column(String(64), nullable=False, index=True)
    factor_id = Column(String(64), nullable=False)
    factor_version = Column(String(32), nullable=False)
    formula_hash = Column(String(80), nullable=False)
    plan_hash = Column(String(80), nullable=False)
    panel_snapshot_id = Column(String(64), nullable=False)
    closed_artifact_hash = Column(String(80), nullable=False)
    validation_config_hash = Column(String(80), nullable=False)
    period_hash = Column(String(80), nullable=False)
    sealed_data_commitment_hash = Column(String(80), nullable=False)
    access_policy_version = Column(String(32), nullable=False)
    approval_reference = Column(String(128), nullable=False)
    requested_by = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="RESERVED")
    recovery_authorization = Column(String(128), nullable=True)
    opened_artifact_id = Column(String(64), nullable=True)
    failure_code = Column(String(64), nullable=True)
    requested_at = Column(DateTime, nullable=False, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)
    audit_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorStatusEvent(QuantBase):
    __tablename__ = "factor_status_events"

    event_id = Column(String(64), primary_key=True)
    factor_id = Column(String(64), nullable=False, index=True)
    factor_version = Column(String(32), nullable=False)
    previous_status = Column(String(32), nullable=False)
    new_status = Column(String(32), nullable=False)
    actor_type = Column(String(32), nullable=False)
    actor_identifier = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    evidence_artifact_id = Column(String(64), nullable=True)
    evidence_run_id = Column(String(64), nullable=True)
    approval_reference = Column(String(128), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorLlmInteraction(QuantBase):
    __tablename__ = "factor_llm_interactions"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_factor_llm_idempotency"),)

    interaction_id = Column(String(64), primary_key=True)
    operation_type = Column(String(64), nullable=False, index=True)
    research_family_id = Column(String(64), nullable=True, index=True)
    hypothesis_id = Column(String(64), nullable=True, index=True)
    factor_id = Column(String(64), nullable=True)
    factor_version = Column(String(32), nullable=True)
    run_id = Column(String(64), nullable=True, index=True)
    attempt_id = Column(String(64), nullable=True)
    provider_id = Column(String(64), nullable=False)
    model_id = Column(String(128), nullable=False)
    prompt_template_id = Column(String(128), nullable=False)
    prompt_template_version = Column(String(32), nullable=False)
    system_prompt_hash = Column(String(80), nullable=False)
    user_prompt_hash = Column(String(80), nullable=False)
    structured_input_hash = Column(String(80), nullable=True)
    structured_output_hash = Column(String(80), nullable=True)
    response_schema_version = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")
    error_code = Column(String(64), nullable=True)
    error_summary = Column(Text, nullable=True)
    input_token_count = Column(Integer, nullable=True)
    output_token_count = Column(Integer, nullable=True)
    total_token_count = Column(Integer, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    finish_reason = Column(String(64), nullable=True)
    idempotency_key = Column(String(128), nullable=True)
    request_payload_hash = Column(String(80), nullable=True)
    actor = Column(String(128), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)


class FactorLlmCandidate(QuantBase):
    __tablename__ = "factor_llm_candidates"

    candidate_id = Column(String(64), primary_key=True)
    interaction_id = Column(String(64), nullable=False, index=True)
    research_family_id = Column(String(64), nullable=True, index=True)
    hypothesis_candidate_id = Column(String(64), nullable=True, index=True)
    candidate_type = Column(String(32), nullable=False, index=True)
    candidate_sequence = Column(Integer, nullable=False, default=1)
    candidate_json = Column(Text, nullable=False)
    candidate_content_hash = Column(String(80), nullable=False, index=True)
    validation_status = Column(String(32), nullable=True)
    formula_hash = Column(String(80), nullable=True, index=True)
    review_status = Column(String(32), nullable=False, default="PENDING_REVIEW")
    reviewed_by = Column(String(128), nullable=True)
    review_reason = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    linked_definition_id = Column(String(64), nullable=True)
    duplicate_of_candidate_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorLlmReviewEvent(QuantBase):
    __tablename__ = "factor_llm_review_events"

    review_event_id = Column(String(64), primary_key=True)
    candidate_id = Column(String(64), nullable=False, index=True)
    previous_status = Column(String(32), nullable=False)
    new_status = Column(String(32), nullable=False)
    actor = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorMiningSession(QuantBase):
    __tablename__ = "factor_mining_sessions"

    session_id = Column(String(64), primary_key=True)
    research_family_id = Column(String(64), nullable=False, index=True)
    research_objective = Column(Text, nullable=False)
    normalized_request_json = Column(Text, nullable=False)
    session_mode = Column(String(32), nullable=False, default="supervised")
    status = Column(String(64), nullable=False, default="DRAFT", index=True)
    actor = Column(String(128), nullable=False)
    authorization_reason = Column(Text, nullable=True)
    snapshot_id = Column(String(64), nullable=True)
    snapshot_identity_hash = Column(String(80), nullable=True)
    data_provider_id = Column(String(64), nullable=False)
    data_source_policy_id = Column(String(64), nullable=False)
    period_split_json = Column(Text, nullable=False)
    period_hash = Column(String(80), nullable=False)
    validation_config_json = Column(Text, nullable=False)
    validation_config_hash = Column(String(80), nullable=False)
    primary_horizon_sessions = Column(Integer, nullable=False)
    prompt_template_set_version = Column(String(64), nullable=False, default="factor-llm-v1")
    field_registry_version = Column(String(64), nullable=False, default="default_v1")
    compiler_version = Column(String(64), nullable=False, default="factor-dsl-v1")
    validation_engine_version = Column(String(64), nullable=False, default="factor-validation-v1")
    multiple_testing_policy_version = Column(String(64), nullable=False, default="distinct_formula_evaluations_v1")
    pause_policy_json = Column(Text, nullable=False)
    pause_policy_hash = Column(String(80), nullable=False)
    stopping_policy_json = Column(Text, nullable=False)
    stopping_policy_hash = Column(String(80), nullable=False)
    budget_policy_json = Column(Text, nullable=False)
    budget_hash = Column(String(80), nullable=False)
    session_config_hash = Column(String(80), nullable=False)
    auto_policy_json = Column(Text, nullable=False, default="{}")
    state_version = Column(Integer, nullable=False, default=0)
    usage_json = Column(Text, nullable=False, default="{}")
    terminal_reason = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    summary_hash = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    authorized_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    pause_reason = Column(Text, nullable=True)
    lease_owner_id = Column(String(128), nullable=True)
    lease_token = Column(String(80), nullable=True)
    lease_acquired_at = Column(DateTime, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    lease_version = Column(Integer, nullable=False, default=0)
    last_heartbeat_at = Column(DateTime, nullable=True)


class FactorMiningLineage(QuantBase):
    __tablename__ = "factor_mining_lineages"

    lineage_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    origin_hypothesis_candidate_id = Column(String(64), nullable=False, index=True)
    current_formula_candidate_id = Column(String(64), nullable=True)
    root_formula_hash = Column(String(80), nullable=True, index=True)
    parent_lineage_id = Column(String(64), nullable=True)
    revision_depth = Column(Integer, nullable=False, default=0)
    status = Column(String(64), nullable=False, default="HYPOTHESIS_PENDING", index=True)
    best_artifact_id = Column(String(64), nullable=True)
    terminal_reason = Column(Text, nullable=True)
    priority_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorMiningEvent(QuantBase):
    __tablename__ = "factor_mining_events"

    event_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    lineage_id = Column(String(64), nullable=True, index=True)
    candidate_id = Column(String(64), nullable=True)
    run_id = Column(String(64), nullable=True)
    previous_state = Column(String(64), nullable=True)
    new_state = Column(String(64), nullable=True)
    event_type = Column(String(64), nullable=False, index=True)
    actor_type = Column(String(32), nullable=False)
    actor_identifier = Column(String(128), nullable=False)
    reason_code = Column(String(64), nullable=True)
    safe_summary = Column(Text, nullable=True)
    budget_snapshot_json = Column(Text, nullable=True)
    family_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorMiningEvaluation(QuantBase):
    __tablename__ = "factor_mining_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "lineage_id",
            "formula_hash",
            "revision_round",
            name="uq_mining_eval_identity",
        ),
    )

    evaluation_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    lineage_id = Column(String(64), nullable=False, index=True)
    formula_candidate_id = Column(String(64), nullable=False)
    factor_id = Column(String(64), nullable=True)
    factor_version = Column(String(32), nullable=True)
    run_id = Column(String(64), nullable=True, index=True)
    artifact_id = Column(String(64), nullable=True)
    formula_hash = Column(String(80), nullable=False, index=True)
    plan_hash = Column(String(80), nullable=True)
    snapshot_id = Column(String(64), nullable=True)
    validation_config_hash = Column(String(80), nullable=False)
    attempt_sequence = Column(Integer, nullable=False, default=1)
    revision_round = Column(Integer, nullable=False, default=0)
    family_size_at_evaluation = Column(Integer, nullable=True)
    acceptance_status = Column(String(32), nullable=True)
    is_duplicate = Column(Boolean, nullable=False, default=False)
    duplicate_of_evaluation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorMiningExposure(QuantBase):
    __tablename__ = "factor_mining_exposures"

    exposure_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    lineage_id = Column(String(64), nullable=True, index=True)
    formula_hash = Column(String(80), nullable=True)
    artifact_id = Column(String(64), nullable=True)
    llm_interaction_id = Column(String(64), nullable=True)
    operation_type = Column(String(64), nullable=False)
    context_tier = Column(String(64), nullable=False)
    prompt_template_version = Column(String(32), nullable=True)
    reservation_status = Column(String(32), nullable=False, default="FINALIZED")
    prompt_template_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorMiningRevisionProposal(QuantBase):
    __tablename__ = "factor_mining_revision_proposals"

    proposal_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False, index=True)
    lineage_id = Column(String(64), nullable=False, index=True)
    parent_formula_candidate_id = Column(String(64), nullable=False)
    parent_formula_hash = Column(String(80), nullable=False)
    child_formula_candidate_id = Column(String(64), nullable=True)
    child_formula_hash = Column(String(80), nullable=True)
    revision_round = Column(Integer, nullable=False, default=1)
    proposal_json = Column(Text, nullable=False)
    ast_diff_json = Column(Text, nullable=True)
    policy_version = Column(String(64), nullable=False, default="bounded_revision_policy_v1")
    policy_status = Column(String(32), nullable=False, default="PENDING")
    critique_interaction_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorPromotionCandidate(QuantBase):
    __tablename__ = "factor_promotion_candidates"

    candidate_id = Column(String(64), primary_key=True)
    factor_id = Column(String(64), nullable=False, index=True)
    factor_version = Column(String(32), nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=False, default="")
    formula_reference = Column(Text, nullable=False, default="")
    source_experiment_ids_json = Column(Text, nullable=False, default="[]")
    source_staging_run_id = Column(String(64), nullable=True, index=True)
    sleeve = Column(String(32), nullable=False, index=True)
    expected_direction = Column(String(32), nullable=False)
    required_data_json = Column(Text, nullable=False, default="[]")
    data_latency_class = Column(String(32), nullable=False, default="daily")
    coverage_statistics_json = Column(Text, nullable=False, default="{}")
    performance_metrics_json = Column(Text, nullable=False, default="{}")
    robustness_summary_json = Column(Text, nullable=False, default="{}")
    transaction_cost_sensitivity_json = Column(Text, nullable=False, default="{}")
    known_weaknesses_json = Column(Text, nullable=False, default="[]")
    version = Column(String(32), nullable=False, default="1.0.0")
    status = Column(String(64), nullable=False, default="experimental", index=True)
    status_reason = Column(Text, nullable=False, default="")
    evidence_bundle_id = Column(String(64), nullable=True)
    evidence_bundle_hash = Column(String(80), nullable=True)
    gate_evaluation_json = Column(Text, nullable=True)
    change_proposal_id = Column(String(64), nullable=True)
    reviewer = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_by = Column(String(128), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorPromotionStatusEvent(QuantBase):
    __tablename__ = "factor_promotion_status_events"

    event_id = Column(String(64), primary_key=True)
    candidate_id = Column(String(64), nullable=False, index=True)
    previous_status = Column(String(64), nullable=True)
    new_status = Column(String(64), nullable=False)
    actor = Column(String(128), nullable=False)
    reason = Column(Text, nullable=False)
    approval_source = Column(String(128), nullable=True)
    evidence_bundle_hash = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class FactorShadowEvaluationRun(QuantBase):
    __tablename__ = "factor_shadow_evaluation_runs"

    run_id = Column(String(64), primary_key=True)
    candidate_id = Column(String(64), nullable=False, index=True)
    sleeve = Column(String(32), nullable=False)
    as_of_date = Column(String(10), nullable=False)
    status = Column(String(32), nullable=False, default="succeeded")
    configuration_version = Column(String(64), nullable=False)
    shadow_weight = Column(String(16), nullable=False, default="0.05")
    observations_json = Column(Text, nullable=False, default="[]")
    disagreement_rate = Column(String(16), nullable=True)
    top_n_membership_changes = Column(Integer, nullable=True)
    concentration_change_json = Column(Text, nullable=False, default="{}")
    error_summary = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
