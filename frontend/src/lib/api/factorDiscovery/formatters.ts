import type { MiningSessionStatus, SessionAllowedActions } from "./types";

const STATUS_LABELS: Record<MiningSessionStatus, string> = {
  DRAFT: "Draft",
  AWAITING_AUTHORIZATION: "Awaiting authorization",
  AUTHORIZED: "Authorized",
  GENERATING_HYPOTHESES: "Generating hypotheses",
  AWAITING_HYPOTHESIS_REVIEW: "Awaiting hypothesis review",
  TRANSLATING_FORMULAS: "Translating formulas",
  AWAITING_FORMULA_REVIEW: "Awaiting formula review",
  READY_TO_LAUNCH: "Ready to launch",
  RUNNING_EXPERIMENTS: "Running experiments",
  ANALYZING_RESULTS: "Analyzing results",
  CRITIQUING_RESULTS: "Critiquing results",
  AWAITING_REVISION_REVIEW: "Awaiting revision review",
  PREPARING_REVISIONS: "Preparing revisions",
  READY_TO_RELAUNCH: "Ready to relaunch",
  PAUSED: "Paused",
  BUDGET_EXHAUSTED: "Budget exhausted",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
  FAILED: "Failed",
};

export function formatMiningStatus(status: string): string {
  return STATUS_LABELS[status as MiningSessionStatus] ?? status.replaceAll("_", " ").toLowerCase();
}

export function miningStatusTone(status: string): "positive" | "negative" | "warning" | "primary" | "muted" {
  if (status === "COMPLETED") return "muted";
  if (status === "FAILED" || status === "CANCELLED" || status === "BUDGET_EXHAUSTED") return "negative";
  if (status.includes("AWAITING") || status === "PAUSED") return "warning";
  if (status === "RUNNING_EXPERIMENTS" || status === "GENERATING_HYPOTHESES") return "primary";
  if (status.includes("PROMISING")) return "positive";
  return "muted";
}

export function pendingReviewTotal(pending: { hypotheses: number; formulas: number; revisions: number }): number {
  return pending.hypotheses + pending.formulas + pending.revisions;
}

export function primaryActionLabel(
  actions: SessionAllowedActions | Record<string, boolean>,
  status: string
): string | null {
  if (actions.can_authorize) return "Authorize";
  if (actions.can_start) return "Start";
  if (actions.can_approve_hypothesis) return "Review hypothesis";
  if (actions.can_approve_formula) return "Review formula";
  if (actions.can_approve_revision) return "Review revision";
  if (actions.can_advance && status === "RUNNING_EXPERIMENTS") return "Refresh";
  if (actions.can_resume) return "Resume";
  if (actions.can_advance) return "Advance";
  return null;
}

export function readinessEntryState(readiness: {
  mining_loop_enabled: boolean;
  factor_discovery_enabled: boolean;
  supervised_ready: boolean;
  blocking_reasons: string[];
}): "disabled" | "partial" | "supervised" {
  if (!readiness.mining_loop_enabled || !readiness.factor_discovery_enabled) return "disabled";
  if (readiness.supervised_ready) return "supervised";
  return "partial";
}
