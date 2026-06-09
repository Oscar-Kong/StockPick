import type { QuantLabLastRunSummary, QuantLabTrustIndicator } from "@/lib/types";

const DEFAULT_SUMMARY = (id: string): QuantLabLastRunSummary => ({
  id,
  available: false,
  reason: "No saved run found",
  stale: false,
  warnings: [],
  trust_indicator: "no_saved_run",
  research_only: false,
});

export function normalizeLastRunSummary(raw: unknown, id: string): QuantLabLastRunSummary {
  if (!raw || typeof raw !== "object") return DEFAULT_SUMMARY(id);
  const o = raw as Record<string, unknown>;
  const main = o.main_metric;
  return {
    id: String(o.id ?? id),
    available: Boolean(o.available),
    reason: o.reason != null ? String(o.reason) : null,
    generated_at: o.generated_at != null ? String(o.generated_at) : null,
    run_id: o.run_id != null ? String(o.run_id) : null,
    sleeve: o.sleeve != null ? String(o.sleeve) : null,
    status: o.status != null ? String(o.status) : null,
    sample_size: typeof o.sample_size === "number" ? o.sample_size : null,
    main_metric:
      main && typeof main === "object"
        ? {
            label: String((main as Record<string, unknown>).label ?? ""),
            value: String((main as Record<string, unknown>).value ?? ""),
          }
        : null,
    stale: Boolean(o.stale),
    stale_reason: o.stale_reason != null ? String(o.stale_reason) : null,
    warnings: Array.isArray(o.warnings) ? o.warnings.map(String) : [],
    trust_indicator: normalizeTrustIndicator(o.trust_indicator),
    research_only: Boolean(o.research_only),
    tab: o.tab != null ? String(o.tab) : null,
  };
}

export function normalizeTrustIndicator(value: unknown): QuantLabTrustIndicator {
  const v = String(value ?? "no_saved_run");
  const allowed: QuantLabTrustIndicator[] = [
    "fresh",
    "stale",
    "insufficient_sample",
    "feature_disabled",
    "no_saved_run",
    "research_only",
    "needs_attention",
  ];
  return allowed.includes(v as QuantLabTrustIndicator) ? (v as QuantLabTrustIndicator) : "no_saved_run";
}

export function normalizeQuantLabEvidence(raw: unknown): {
  sleeve: string;
  generated_at: string;
  validation_copy: string;
  factor_ic: QuantLabLastRunSummary;
  walk_forward: QuantLabLastRunSummary;
  predictions: QuantLabLastRunSummary;
  pairs: QuantLabLastRunSummary;
  jobs: QuantLabLastRunSummary;
} {
  const o = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    sleeve: String(o.sleeve ?? "medium"),
    generated_at: String(o.generated_at ?? ""),
    validation_copy: String(
      o.validation_copy ??
        "Quant Lab validates the scoring system. It does not automatically change scan rankings."
    ),
    factor_ic: normalizeLastRunSummary(o.factor_ic, "factor_ic"),
    walk_forward: normalizeLastRunSummary(o.walk_forward, "walk_forward"),
    predictions: normalizeLastRunSummary(o.predictions, "predictions"),
    pairs: normalizeLastRunSummary(o.pairs, "pairs"),
    jobs: normalizeLastRunSummary(o.jobs, "jobs"),
  };
}

export const LAST_RUN_CARD_ORDER = [
  "factor_ic",
  "walk_forward",
  "predictions",
  "pairs",
  "jobs",
] as const;

export type LastRunCardId = (typeof LAST_RUN_CARD_ORDER)[number];

export function evidenceCards(
  evidence: ReturnType<typeof normalizeQuantLabEvidence>
): QuantLabLastRunSummary[] {
  return LAST_RUN_CARD_ORDER.map((id) => evidence[id]);
}

/** User-triggered research tabs — show "Run new research" button. */
export const USER_TRIGGERED_LAST_RUN_IDS = new Set<LastRunCardId>([
  "walk_forward",
  "pairs",
]);

export function formatEvidenceDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = iso.slice(0, 10);
  return d || "—";
}
