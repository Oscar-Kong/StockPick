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

/** Headline score for the scan table SCORE column. */
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

/** Pillar chips are disabled in the scan table — SCORE is a single number. */
export function hasInformativePillarBreakdown(_parts: ScanScoreParts): boolean {
  return false;
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

/** Always empty — scan SCORE column stays a single number (Action carries buy/wait). */
export function displayPillars(_parts: ScanScoreParts): DisplayPillar[] {
  return [];
}
