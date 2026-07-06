/** Factor Discovery mining workspace types (Phase 8B). */

export type MiningSessionStatus =
  | "DRAFT"
  | "AWAITING_AUTHORIZATION"
  | "AUTHORIZED"
  | "GENERATING_HYPOTHESES"
  | "AWAITING_HYPOTHESIS_REVIEW"
  | "TRANSLATING_FORMULAS"
  | "AWAITING_FORMULA_REVIEW"
  | "READY_TO_LAUNCH"
  | "RUNNING_EXPERIMENTS"
  | "ANALYZING_RESULTS"
  | "CRITIQUING_RESULTS"
  | "AWAITING_REVISION_REVIEW"
  | "PREPARING_REVISIONS"
  | "READY_TO_RELAUNCH"
  | "PAUSED"
  | "BUDGET_EXHAUSTED"
  | "COMPLETED"
  | "CANCELLED"
  | "FAILED";

export type MiningSessionMode = "supervised" | "bounded_auto";

export interface PendingReviews {
  hypotheses: number;
  formulas: number;
  revisions: number;
}

export interface SessionAllowedActions {
  can_authorize: boolean;
  can_start: boolean;
  can_advance: boolean;
  can_pause: boolean;
  can_resume: boolean;
  can_cancel: boolean;
  can_approve_hypothesis: boolean;
  can_reject_hypothesis: boolean;
  can_approve_formula: boolean;
  can_reject_formula: boolean;
  can_approve_revision: boolean;
  can_reject_revision: boolean;
}

export interface MiningMutationEnvelope {
  session_id: string;
  prior_status?: string | null;
  status: MiningSessionStatus;
  state_version: number;
  pause_reason?: string | null;
  stop_reason?: string | null;
  pending_reviews: PendingReviews;
  active_lineage_count: number;
  budget_summary: Record<string, number>;
  allowed_actions: SessionAllowedActions;
  action_disabled_reasons?: Record<string, string>;
  events_created: string[];
  warnings: string[];
}

export interface MiningSessionListItem {
  session_id: string;
  session_name?: string | null;
  research_objective: string;
  status: MiningSessionStatus;
  session_mode: MiningSessionMode;
  research_family_id: string;
  state_version: number;
  active_lineage_count: number;
  pending_reviews: PendingReviews;
  promising_candidate_count: number;
  experiments_count: number;
  budget_used: Record<string, number>;
  validation_exposures: number;
  updated_at?: string | null;
}

export interface MiningSessionDetail extends MiningSessionListItem {
  pause_reason?: string | null;
  terminal_reason?: string | null;
  data_provider_id: string;
  created_at?: string | null;
  immutable_config: Record<string, unknown>;
  policies: Record<string, unknown>;
  budget: Record<string, number>;
  usage: Record<string, number>;
  budget_remaining: Record<string, number>;
  lineages: Array<{
    lineage_id: string;
    status: string;
    revision_depth: number;
    root_formula_hash?: string | null;
    terminal_reason?: string | null;
    origin_hypothesis_candidate_id: string;
    current_formula_candidate_id?: string | null;
    best_artifact_id?: string | null;
  }>;
  evaluations: Array<{
    evaluation_id: string;
    lineage_id: string;
    run_id?: string | null;
    artifact_id?: string | null;
    formula_hash?: string | null;
    revision_round: number;
    is_duplicate: boolean;
  }>;
  pending_approval_count: number;
  recent_events: Array<{
    event_id: string;
    event_type: string;
    previous_state?: string | null;
    new_state?: string | null;
    created_at?: string | null;
  }>;
  allowed_actions: SessionAllowedActions;
  action_disabled_reasons: Record<string, string>;
  integrity_status: string;
  no_sealed_access: boolean;
  no_lifecycle_promotion: boolean;
}

export interface MiningReadiness {
  factor_discovery_enabled: boolean;
  factor_discovery_llm_enabled: boolean;
  mining_loop_enabled: boolean;
  current_mining_mode: string;
  supervised_ready: boolean;
  bounded_auto_ready: boolean;
  llm_provider_ready: boolean;
  llm_provider?: string | null;
  llm_model?: string | null;
  data_provider_ready: boolean;
  data_provider?: string | null;
  snapshot_ready: boolean;
  pit_universe_ready: boolean;
  adjusted_prices_ready: boolean;
  historical_store_ready: boolean;
  pit_fundamentals_ready: boolean;
  sector_history_ready: boolean;
  industry_history_ready: boolean;
  market_cap_history_ready: boolean;
  supported_fields: string[];
  supported_field_groups: Record<string, string[]>;
  blocking_reasons: string[];
  warnings: string[];
  no_sealed_access: boolean;
  no_production_integration: boolean;
  infrastructure: Record<string, number | boolean>;
  budget_defaults: Record<string, number>;
  staging_research_readiness?: {
    label: string;
    not_trading_readiness: boolean;
    staging_enabled: boolean;
    blocking_reasons: string[];
    latest_audit_status?: string | null;
    limitations: string[];
    price_coverage?: Record<string, unknown>;
    universe_coverage?: Record<string, unknown>;
    provider_capabilities?: Record<string, unknown>;
  };
}

export interface ResearchFamilyItem {
  family_id: string;
  research_objective: string;
  intended_universe: string;
  primary_horizon_sessions: number;
  closed: boolean;
  formula_attempt_count: number;
  multiple_testing_policy: string;
  created_at?: string | null;
}

export interface MiningEventItem {
  event_id: string;
  event_type: string;
  previous_state?: string | null;
  new_state?: string | null;
  created_at?: string | null;
}

export interface LlmCandidateItem {
  candidate_id: string;
  candidate_type: string;
  review_status: string;
  validation_status?: string | null;
  interaction_id?: string | null;
}

export type FactorDiscoveryView = "sessions" | "new-research" | "review-queue" | "factors" | "readiness";

export type IntegrityStatus = "VERIFIED" | "NOT_VERIFIED" | "FAILED" | "UNAVAILABLE";

export interface ReviewAllowedActions {
  can_approve: boolean;
  can_reject: boolean;
}

export interface ReviewQueueItem {
  review_type: "hypothesis" | "formula" | "revision" | "promising";
  candidate_id: string;
  candidate_name: string;
  session_id: string | null;
  session_name?: string | null;
  state_version: number | null;
  research_family_id?: string | null;
  lineage_id?: string;
  artifact_id?: string | null;
  created_at?: string | null;
  review_reason: string;
  warning_count: number;
  risk_level: string;
}

export interface HypothesisCandidateDetail {
  candidate_id: string;
  session_id: string | null;
  state_version: number | null;
  candidate_name?: string;
  economic_rationale?: string;
  expected_mechanism?: string;
  expected_direction?: string;
  intended_universe?: string;
  holding_period_sessions?: number;
  rebalance_frequency?: string;
  required_data_classes?: string[];
  proposed_fields?: string[];
  deterministic_support_status?: string;
  known_risks?: string[];
  expected_failure_conditions?: string[];
  expected_turnover?: string;
  benchmark_overlap?: string;
  assumptions?: string[];
  critique?: { critique_candidate_id: string; interaction_id: string; summary: Record<string, unknown> } | null;
  review_status: string;
  allowed_actions: ReviewAllowedActions;
}

export interface FormulaCandidateDetail {
  candidate_id: string;
  session_id: string | null;
  state_version: number | null;
  proposed_factor_name?: string;
  canonical_dsl?: string;
  original_llm_dsl?: string;
  formula_hash?: string;
  plan_hash?: string;
  expected_direction?: string;
  compiler_required_fields?: string[];
  compiler_warnings?: string[];
  compile_status?: string;
  ast_node_count?: number;
  ast_depth?: number;
  operators_used?: string[];
  canonical_ast?: unknown;
  formula_review?: { summary: Record<string, unknown> } | null;
  duplicate_status?: string;
  review_status: string;
  allowed_actions: ReviewAllowedActions;
}

export interface RevisionCandidateDetail {
  candidate_id: string;
  session_id: string | null;
  state_version: number | null;
  parent_canonical_dsl?: string;
  proposed_canonical_dsl?: string;
  revision_rationale?: string;
  failure_categories_addressed?: string[];
  fields_added?: string[];
  fields_removed?: string[];
  node_count_delta?: number;
  depth_delta?: number;
  structural_similarity?: string;
  exact_duplicate?: boolean;
  near_duplicate?: boolean;
  revision_policy_rules?: unknown[];
  policy_result?: string;
  review_status: string;
  allowed_actions: ReviewAllowedActions;
}

export interface ValidationResultDetail {
  artifact_id: string;
  run_id: string;
  identity: Record<string, unknown>;
  integrity: {
    integrity_status: IntegrityStatus;
    integrity_checked_at?: string | null;
    integrity_error_code?: string | null;
    integrity_error_summary?: string | null;
  };
  overview: Record<string, unknown>;
  signal: Record<string, unknown>;
  quantiles: Record<string, unknown>;
  portfolio: Record<string, unknown>;
  walk_forward: Record<string, unknown>;
  robustness: Record<string, unknown>;
  redundancy: Record<string, unknown>;
  statistical: Record<string, unknown>;
  multiple_testing: Record<string, unknown>;
  acceptance: Record<string, unknown>;
  promising_policy: Record<string, unknown> | null;
  limitations: string[];
  trust_metrics: boolean;
  no_sealed_metrics: boolean;
}

export interface FactorRegistryItem {
  factor_id: string;
  latest_version: string;
  display_name: string;
  lifecycle_status: string;
  expected_direction: string;
  canonical_dsl_summary: string;
  required_fields: string[];
  latest_run_id?: string | null;
  latest_artifact_id?: string | null;
  latest_acceptance_status?: string | null;
  latest_promising_status?: boolean;
  version_count: number;
  updated_at?: string | null;
}

export type FactorPromotionStatus =
  | "experimental"
  | "staged"
  | "promotion_candidate"
  | "shadow"
  | "approved_for_manual_integration"
  | "rejected"
  | "archived";

export interface PromotionGateResult {
  gate_id: string;
  display_name: string;
  verdict: "pass" | "fail" | "not_applicable" | "warning";
  threshold?: string | null;
  observed?: string | null;
  explanation: string;
  blocking: boolean;
}

export interface FactorPromotionCandidateSummary {
  candidate_id: string;
  factor_id: string;
  factor_version: string;
  display_name: string;
  sleeve: string;
  status: FactorPromotionStatus;
  expected_direction: string;
  source_staging_run_id?: string | null;
  evidence_bundle_hash?: string | null;
  gate_overall_pass?: boolean | null;
  created_at: string;
  reviewed_at?: string | null;
  reviewer?: string | null;
  advisory_only: boolean;
  affects_live_ranking: boolean;
}

export interface FactorPromotionCandidateDetail extends FactorPromotionCandidateSummary {
  description: string;
  formula_reference: string;
  required_data: string[];
  known_weaknesses: string[];
  status_reason: string;
  latest_gate_evaluation?: {
    overall_pass: boolean;
    blocking_failures: string[];
    gates: PromotionGateResult[];
  } | null;
}

export interface PromotionEvidenceBundle {
  bundle_id: string;
  bundle_hash: string;
  summary: string;
  gate_evaluation?: FactorPromotionCandidateDetail["latest_gate_evaluation"];
  failure_modes: string[];
  negative_controls: Record<string, unknown>[];
  llm_summary_disclaimer: string;
}

export interface PromotionAuditHistoryResponse {
  candidate_id: string;
  events: Array<{
    event_id: string;
    previous_status?: string | null;
    new_status: string;
    actor: string;
    reason: string;
    created_at: string;
  }>;
}

export interface ShadowEvaluationRun {
  run_id: string;
  candidate_id: string;
  sleeve: string;
  as_of_date: string;
  status: string;
  shadow_weight: number;
  disagreement_rate?: number | null;
  top_n_membership_changes?: number | null;
  live_scores_preserved: boolean;
  live_rankings_preserved: boolean;
  observations: Array<{
    symbol: string;
    live_rank?: number | null;
    shadow_rank?: number | null;
    rank_change?: number | null;
    live_score: number;
    shadow_score: number;
    score_change: number;
    candidate_contribution: number;
  }>;
}
