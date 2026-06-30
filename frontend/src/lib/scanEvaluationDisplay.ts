import type { ResearchRunDetailResponse } from "@/lib/types";

export type ComparisonRow = Record<string, string | number | null | undefined>;

export const SCAN_EVAL_ALGORITHM_VERSIONS = [
  "alphabetical_baseline",
  "stage_a_v1",
  "stage_a_v2",
  "scoring_engine_v1",
] as const;

export type ScanEvalAlgorithmVersion = (typeof SCAN_EVAL_ALGORITHM_VERSIONS)[number];

const ALGORITHM_LABELS: Record<string, string> = {
  alphabetical_baseline: "Alphabetical baseline",
  stage_a_v1: "Stage A v1",
  stage_a_v2: "Stage A v2",
  scoring_engine_v1: "Scoring engine v1",
};

export function displayAlgorithmName(version: string): string {
  return ALGORITHM_LABELS[version] ?? version.replace(/_/g, " ");
}

export function extractComparisonTable(detail: ResearchRunDetailResponse["detail"]): ComparisonRow[] {
  const ql = (detail?.quant_lab ?? {}) as Record<string, unknown>;
  if (Array.isArray(ql.comparison_table)) return ql.comparison_table as ComparisonRow[];
  const nested = detail?.comparison as Record<string, unknown> | undefined;
  if (nested && Array.isArray(nested.metrics_table)) return nested.metrics_table as ComparisonRow[];
  return [];
}

export function extractCaveats(detail: ResearchRunDetailResponse["detail"]): string[] {
  const raw = detail?.caveats;
  if (Array.isArray(raw)) return raw.map(String);
  return [];
}

export function formatMetric(value: unknown, style: "percent" | "decimal" | "raw" = "decimal"): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (!Number.isFinite(n)) return String(value);
  if (style === "percent") return `${(n * 100).toFixed(1)}%`;
  if (style === "decimal") return n.toFixed(3);
  return String(n);
}

export function pickBestRecallRow(rows: ComparisonRow[]): ComparisonRow | null {
  if (!rows.length) return null;
  return rows.reduce((best, row) => {
    const cur = Number(row.recall_at_10);
    const bestVal = Number(best.recall_at_10);
    if (!Number.isFinite(cur)) return best;
    if (!Number.isFinite(bestVal)) return row;
    return cur > bestVal ? row : best;
  }, rows[0]);
}

export function scanEvalRunContext(detail: ResearchRunDetailResponse): {
  bucket: string;
  startDate: string;
  endDate: string;
  versions: string[];
} {
  const detailObj = detail.detail as Record<string, unknown> | undefined;
  const config = detailObj?.config as Record<string, unknown> | undefined;
  const params = (detailObj?.parameters ?? config?.parameters ?? detail.summary.parameters) as
    | Record<string, unknown>
    | undefined;
  const versionsRaw = params?.algorithm_versions;
  const versions = Array.isArray(versionsRaw)
    ? versionsRaw.map(String)
    : typeof versionsRaw === "string"
      ? versionsRaw.split(",").map((v) => v.trim()).filter(Boolean)
      : extractComparisonTable(detail.detail).map((r) => String(r.algorithm_version ?? ""));
  return {
    bucket: String(params?.bucket ?? detail.summary.sleeve ?? "—"),
    startDate: String(params?.start_date ?? "—"),
    endDate: String(params?.end_date ?? "—"),
    versions,
  };
}
