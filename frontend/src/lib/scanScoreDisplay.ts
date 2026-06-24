import type { StockResult } from "@/lib/types";

/** Backend default when confidence / tradability data is missing or neutral. */
export const NEUTRAL_PILLAR_SCORE = 50;
const NEUTRAL_EPSILON = 1.5;

export type ScanPillarKey = "alpha_score" | "confidence_score" | "tradability_score";

export interface ScanScoreParts {
  ranking: number;
  alpha: number | null;
  confidence: number | null;
  tradability: number | null;
}

export function readPillar(stock: StockResult, key: ScanPillarKey): number | null {
  const top = stock[key];
  if (typeof top === "number" && Number.isFinite(top)) return top;
  const nested = stock.metrics?.[key];
  if (typeof nested === "number" && Number.isFinite(nested)) return nested;
  return null;
}

export function readRankingScore(stock: StockResult): number {
  if (typeof stock.ranking_score === "number" && Number.isFinite(stock.ranking_score)) {
    return stock.ranking_score;
  }
  const nested = stock.metrics?.ranking_score;
  if (typeof nested === "number" && Number.isFinite(nested)) return nested;
  return stock.score;
}

export function readScanScoreParts(stock: StockResult): ScanScoreParts {
  return {
    ranking: readRankingScore(stock),
    alpha: readPillar(stock, "alpha_score"),
    confidence: readPillar(stock, "confidence_score"),
    tradability: readPillar(stock, "tradability_score"),
  };
}

export function isNeutralPillar(value: number | null | undefined): boolean {
  if (value == null || !Number.isFinite(value)) return true;
  return Math.abs(value - NEUTRAL_PILLAR_SCORE) <= NEUTRAL_EPSILON;
}

/** True when decomposed pillars add information beyond the composite ranking. */
export function hasInformativePillarBreakdown(parts: ScanScoreParts): boolean {
  const confInformative = parts.confidence != null && !isNeutralPillar(parts.confidence);
  const tradeInformative = parts.tradability != null && !isNeutralPillar(parts.tradability);
  return confInformative || tradeInformative;
}

export function hasDecomposedScores(stock: StockResult): boolean {
  const parts = readScanScoreParts(stock);
  return parts.alpha != null || parts.confidence != null || parts.tradability != null;
}

export type DisplayPillar = {
  key: "alpha" | "confidence" | "trade";
  metricKey: ScanPillarKey;
  value: number;
};

/** Pillars worth showing — skips neutral confidence/tradability placeholders. */
export function displayPillars(parts: ScanScoreParts): DisplayPillar[] {
  const out: DisplayPillar[] = [];
  if (parts.alpha != null && !isNeutralPillar(parts.alpha)) {
    out.push({ key: "alpha", metricKey: "alpha_score", value: parts.alpha });
  }
  if (parts.confidence != null && !isNeutralPillar(parts.confidence)) {
    out.push({ key: "confidence", metricKey: "confidence_score", value: parts.confidence });
  }
  if (parts.tradability != null && !isNeutralPillar(parts.tradability)) {
    out.push({ key: "trade", metricKey: "tradability_score", value: parts.tradability });
  }
  return out;
}
