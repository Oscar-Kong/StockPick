import type { DailyDashboardResponse, PortfolioDecisionItem } from "@/lib/types";

export type DecisionTone = "buy" | "keep" | "sell" | "review";
export type CockpitStatus = "ready" | "needs_review" | "demo" | "import_needed" | "stale" | "fresh" | "updating" | "missing";
export type AlertSeverity = "critical" | "warning" | "info";

const STALE_MS = 24 * 60 * 60 * 1000;

export function formatCurrency(value: number, opts?: { compact?: boolean }): string {
  if (opts?.compact && Math.abs(value) >= 1000) {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  return `$${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatShares(shares: number): string {
  if (Number.isInteger(shares)) return shares.toLocaleString();
  return shares.toLocaleString(undefined, { maximumFractionDigits: 6 });
}

export function formatDecision(decision: string): string {
  return decision.replace(/_/g, " ").toUpperCase();
}

export function getDecisionTone(decision: string): DecisionTone {
  const d = decision.toLowerCase();
  if (d === "buy") return "buy";
  if (d === "sell" || d === "trim") return "sell";
  if (d === "review") return "review";
  return "keep";
}

export function getDecisionPriority(decision: string): number {
  const tone = getDecisionTone(decision);
  if (tone === "sell") return 0;
  if (tone === "review") return 1;
  if (tone === "buy") return 2;
  return 3;
}

export function filterActiveDecisionItems(items: PortfolioDecisionItem[]): PortfolioDecisionItem[] {
  return items.filter((i) => i.bucket !== "medium");
}

export function buildActionQueue(items: PortfolioDecisionItem[]): PortfolioDecisionItem[] {
  return filterActiveDecisionItems(items)
    .filter((i) => getDecisionPriority(i.decision) < 3)
    .sort((a, b) => getDecisionPriority(a.decision) - getDecisionPriority(b.decision));
}

export function inferAlertSeverity(text: string): AlertSeverity {
  const lower = text.toLowerCase();
  if (/missing|review|sell|stop|trim|urgent/.test(lower)) return "critical";
  if (/overweight|high-risk|high risk|penny/.test(lower)) return "warning";
  return "info";
}

export function getCockpitStatus(data: DailyDashboardResponse): CockpitStatus {
  const freshness = data.freshness?.overall_status;
  if (freshness === "demo" || data.is_demo_data) return "demo";
  if (freshness === "updating") return "updating";
  if (freshness === "missing") return "import_needed";
  if (freshness === "stale") return "stale";
  if (freshness === "fresh") return "fresh";
  if (data.is_demo_data) return "demo";
  if (!data.holdings.length) return "import_needed";
  const items = filterActiveDecisionItems(data.decision?.items ?? []);
  if (items.some((i) => getDecisionTone(i.decision) === "review")) return "needs_review";
  if (data.decision_stale_warning || data.freshness?.refresh_recommended) return "stale";
  if (data.last_decision_run_at) {
    const age = Date.now() - new Date(data.last_decision_run_at).getTime();
    if (age > STALE_MS) return "stale";
  } else if (data.holdings.length > 0) {
    return "stale";
  }
  const realSource = data.data_source === "csv" || data.data_source === "snaptrade";
  if (realSource && data.decision?.items?.length) return "ready";
  if (data.holdings.length && !data.decision?.items?.length) return "stale";
  return "ready";
}

export function rowAccentClass(decision: string): string {
  const tone = getDecisionTone(decision);
  if (tone === "sell") return "border-l-[3px] border-l-negative/80";
  if (tone === "review") return "border-l-[3px] border-l-amber-500/70";
  if (tone === "buy") return "border-l-[3px] border-l-brand/70";
  return "border-l-[3px] border-l-transparent";
}

export function actionSummary(item: PortfolioDecisionItem): string {
  if (item.suggested_action?.trim()) return item.suggested_action;
  if (item.reasons[0]) return item.reasons[0];
  return `${formatDecision(item.decision)} — ${item.sell_pct.toFixed(0)}% sell / ${item.keep_pct.toFixed(0)}% keep / ${item.buy_pct.toFixed(0)}% buy`;
}
