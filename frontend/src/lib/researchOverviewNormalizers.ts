import type {
  EvidenceMaintenanceAction,
  GenerateIdeasResponse,
  ResearchBriefFinding,
  ResearchIdea,
  ResearchIdeaListResponse,
  ResearchOverviewResponse,
  ResearchActivityItem,
} from "./types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return value != null && typeof value === "object" && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function normalizeResearchBriefFinding(raw: unknown): ResearchBriefFinding | null {
  if (!isRecord(raw)) return null;
  const findingId = asString(raw.finding_id);
  const title = asString(raw.title);
  if (!findingId || !title) return null;
  return {
    finding_id: findingId,
    title,
    explanation: asString(raw.explanation) ?? "",
    supporting_metric: asString(raw.supporting_metric) ?? "",
    source_reference: asString(raw.source_reference) ?? "",
    why_it_matters: asString(raw.why_it_matters) ?? "",
    confidence: asNumber(raw.confidence) ?? 0,
    evidence_impact: asString(raw.evidence_impact) ?? "informational",
    suggested_experiment_type: asString(raw.suggested_experiment_type) ?? "factor_validation",
    suggested_parameters: isRecord(raw.suggested_parameters) ? raw.suggested_parameters : {},
  };
}

export function normalizeResearchIdea(raw: unknown): ResearchIdea | null {
  if (!isRecord(raw)) return null;
  const id = asString(raw.id);
  const title = asString(raw.title);
  if (!id || !title) return null;
  return {
    id,
    title,
    hypothesis: asString(raw.hypothesis) ?? "",
    description: asString(raw.description) ?? "",
    why_now: asString(raw.why_now) ?? "",
    source_type: (asString(raw.source_type) ?? "user_created") as ResearchIdea["source_type"],
    source_references: Array.isArray(raw.source_references) ? raw.source_references.map(String) : [],
    sleeve: asString(raw.sleeve),
    universe_definition: isRecord(raw.universe_definition) ? raw.universe_definition : {},
    suggested_experiment_type: asString(raw.suggested_experiment_type),
    suggested_parameters: isRecord(raw.suggested_parameters) ? raw.suggested_parameters : {},
    priority: asNumber(raw.priority) ?? 50,
    confidence: asNumber(raw.confidence) ?? 0.5,
    status: (asString(raw.status) ?? "new") as ResearchIdea["status"],
    user_notes: asString(raw.user_notes) ?? "",
    created_at: asString(raw.created_at) ?? "",
    updated_at: asString(raw.updated_at) ?? "",
  };
}

function normalizeActivity(raw: unknown): ResearchActivityItem | null {
  if (!isRecord(raw)) return null;
  const id = asString(raw.id);
  const label = asString(raw.label);
  if (!id || !label) return null;
  return {
    id,
    activity_type: asString(raw.activity_type) ?? "activity",
    label,
    occurred_at: asString(raw.occurred_at),
    status: asString(raw.status),
    run_id: asString(raw.run_id),
  };
}

function normalizeMaintenance(raw: unknown): EvidenceMaintenanceAction | null {
  if (!isRecord(raw)) return null;
  const actionId = asString(raw.action_id);
  const label = asString(raw.label);
  const endpoint = asString(raw.endpoint);
  if (!actionId || !label || !endpoint) return null;
  return {
    action_id: actionId,
    label,
    description: asString(raw.description) ?? "",
    endpoint,
    method: asString(raw.method) ?? "POST",
    available: raw.available !== false,
    reason_unavailable: asString(raw.reason_unavailable),
  };
}

export function normalizeResearchOverviewResponse(raw: unknown): ResearchOverviewResponse {
  if (!isRecord(raw)) {
    return {
      generated_at: "",
      sleeve: "penny",
      research_confidence_status: "insufficient_data",
      research_confidence_score: 0,
      data_freshness: "unknown",
      strategy_version: "",
      factor_model_version: "",
      predictions_resolved: 0,
      predictions_unresolved: 0,
      failed_or_blocked_jobs: 0,
      major_warnings: [],
      findings: [],
      recommended_ideas: [],
      recent_activity: [],
      maintenance_actions: [],
    };
  }
  const findings = Array.isArray(raw.findings)
    ? raw.findings.map(normalizeResearchBriefFinding).filter((f): f is ResearchBriefFinding => f != null)
    : [];
  const recommended = Array.isArray(raw.recommended_ideas)
    ? raw.recommended_ideas.map(normalizeResearchIdea).filter((i): i is ResearchIdea => i != null)
    : [];
  const activity = Array.isArray(raw.recent_activity)
    ? raw.recent_activity.map(normalizeActivity).filter((a): a is ResearchActivityItem => a != null)
    : [];
  const maintenance = Array.isArray(raw.maintenance_actions)
    ? raw.maintenance_actions.map(normalizeMaintenance).filter((m): m is EvidenceMaintenanceAction => m != null)
    : [];

  return {
    generated_at: asString(raw.generated_at) ?? "",
    sleeve: asString(raw.sleeve) ?? "penny",
    research_confidence_status: asString(raw.research_confidence_status) ?? "insufficient_data",
    research_confidence_score: asNumber(raw.research_confidence_score) ?? 0,
    data_freshness: asString(raw.data_freshness) ?? "unknown",
    strategy_version: asString(raw.strategy_version) ?? "",
    factor_model_version: asString(raw.factor_model_version) ?? "",
    market_regime: asString(raw.market_regime),
    predictions_resolved: asNumber(raw.predictions_resolved) ?? 0,
    predictions_unresolved: asNumber(raw.predictions_unresolved) ?? 0,
    failed_or_blocked_jobs: asNumber(raw.failed_or_blocked_jobs) ?? 0,
    major_warnings: Array.isArray(raw.major_warnings) ? raw.major_warnings.map(String) : [],
    findings,
    recommended_ideas: recommended,
    recent_activity: activity,
    maintenance_actions: maintenance,
  };
}

export function normalizeResearchIdeaListResponse(raw: unknown): ResearchIdeaListResponse {
  if (!isRecord(raw)) return { ideas: [], total: 0, offset: 0, limit: 50 };
  const ideas = Array.isArray(raw.ideas)
    ? raw.ideas.map(normalizeResearchIdea).filter((i): i is ResearchIdea => i != null)
    : [];
  return {
    ideas,
    total: asNumber(raw.total) ?? ideas.length,
    offset: asNumber(raw.offset) ?? 0,
    limit: asNumber(raw.limit) ?? 50,
  };
}

export function normalizeGenerateIdeasResponse(raw: unknown): GenerateIdeasResponse {
  if (!isRecord(raw)) return { created: [], skipped_duplicates: 0, findings_used: 0 };
  const created = Array.isArray(raw.created)
    ? raw.created.map(normalizeResearchIdea).filter((i): i is ResearchIdea => i != null)
    : [];
  return {
    created,
    skipped_duplicates: asNumber(raw.skipped_duplicates) ?? 0,
    findings_used: asNumber(raw.findings_used) ?? 0,
  };
}
