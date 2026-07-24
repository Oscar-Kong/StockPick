import { readRankingScore } from "@/lib/scanScoreDisplay";
import type { StockResult } from "@/lib/types";

/** Recalibrated bands for real Stage B ranking scores (not the old fallback 90+ rule). */
export const SCAN_SCORE_STRONG_MIN = 70;
export const SCAN_SCORE_WATCH_MIN = 65;

export type ScanScoreBand = "strong" | "watch" | "skip" | "fallback";

export function isPartialDataFallback(stock: StockResult): boolean {
  return Boolean(stock.metrics?.provider_limited_partial_data);
}

export function scoreBandForStock(stock: StockResult): ScanScoreBand {
  if (isPartialDataFallback(stock)) return "fallback";
  const score = readRankingScore(stock);
  if (score >= SCAN_SCORE_STRONG_MIN) return "strong";
  if (score >= SCAN_SCORE_WATCH_MIN) return "watch";
  return "skip";
}

/** 0–100 percentile of this score within the current result list (higher = better). */
export function scorePercentileInScan(score: number, scanScores: number[]): number | null {
  const finite = scanScores.filter((s) => Number.isFinite(s));
  if (finite.length === 0) return null;
  if (finite.length === 1) return 100;
  const below = finite.filter((s) => s < score).length;
  const equal = finite.filter((s) => s === score).length;
  return Math.round(((below + equal * 0.5) / finite.length) * 100);
}
