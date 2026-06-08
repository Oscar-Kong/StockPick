/**
 * Quant v2 score helpers — primary display resolution and safe field access.
 */
import type { AnalyzeSymbolResponse, Bucket, RiskLevel, Signal, V2ScoreResponse } from "./types";

export type ScoreSource = "scoring_engine_v2" | "legacy_screener";

export type V2UnavailableReason = "disabled" | "not_found" | "error";

export interface AnalysisDisplay {
  scoreSource: ScoreSource;
  score: number;
  riskLevel: RiskLevel | string;
  summary: string;
  signals: Signal[];
  hasV2: boolean;
  legacyScore: number;
}

export function parseV2FetchError(err: unknown): V2UnavailableReason {
  const msg = err instanceof Error ? err.message : String(err);
  if (msg.includes("503") || msg.toLowerCase().includes("score_engine_v2_enabled")) {
    return "disabled";
  }
  if (msg.includes("404") || msg.toLowerCase().includes("not found")) {
    return "not_found";
  }
  return "error";
}

export function isV2ScoreResponse(value: unknown): value is V2ScoreResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.symbol === "string" &&
    typeof v.sleeve === "string" &&
    typeof v.score === "number" &&
    Array.isArray(v.factors)
  );
}

export function hasV2Factors(score: V2ScoreResponse | null | undefined): score is V2ScoreResponse {
  return Boolean(score && Array.isArray(score.factors) && score.factors.length > 0);
}

export function hasV2Recommendation(score: V2ScoreResponse | null | undefined): boolean {
  return Boolean(score?.recommendation?.recommendation);
}

export function factorsToSignals(score: V2ScoreResponse): Signal[] {
  return (score.factors ?? []).map((f) => ({
    name: f.display_name || f.factor_id,
    value: f.norm_score ?? 0,
    weight: f.weight ?? 0,
    contribution: f.contribution ?? 0,
    description: f.description ?? "",
  }));
}

export function resolveAnalysisDisplay(
  legacy: AnalyzeSymbolResponse,
  v2: V2ScoreResponse | null | undefined
): AnalysisDisplay {
  if (isV2ScoreResponse(v2)) {
    return {
      scoreSource: "scoring_engine_v2",
      score: v2.score,
      riskLevel: v2.risk_level ?? legacy.risk_level,
      summary: v2.summary || legacy.summary,
      signals: hasV2Factors(v2) ? factorsToSignals(v2) : legacy.signals,
      hasV2: true,
      legacyScore: legacy.score,
    };
  }
  return {
    scoreSource: "legacy_screener",
    score: legacy.score,
    riskLevel: legacy.risk_level,
    summary: legacy.summary,
    signals: legacy.signals,
    hasV2: false,
    legacyScore: legacy.score,
  };
}

export function scoreSourcesDiffer(display: AnalysisDisplay): boolean {
  return display.hasV2 && Math.abs(display.score - display.legacyScore) >= 0.05;
}

export function safeAttribution(score: V2ScoreResponse | null | undefined) {
  return score?.attribution ?? null;
}

export function safeRiskBreakdown(score: V2ScoreResponse | null | undefined) {
  return score?.risk ?? null;
}

export function bucketForV2(legacy: AnalyzeSymbolResponse, bucket?: Bucket): Bucket {
  return (bucket ?? legacy.assigned_bucket) as Bucket;
}
