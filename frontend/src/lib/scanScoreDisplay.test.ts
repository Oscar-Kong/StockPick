import { describe, expect, it } from "vitest";
import {
  displayPillars,
  hasInformativePillarBreakdown,
  isNeutralPillar,
  readRankingScore,
  readScanScoreParts,
} from "./scanScoreDisplay";
import type { StockResult } from "./types";

function stock(overrides: Partial<StockResult> = {}): StockResult {
  return {
    symbol: "TEST",
    score: 72,
    price: 10,
    risk_level: "medium",
    signals: [],
    metrics: {},
    ...overrides,
  } as StockResult;
}

describe("scanScoreDisplay", () => {
  it("treats ~50 as neutral pillar placeholder", () => {
    expect(isNeutralPillar(50)).toBe(true);
    expect(isNeutralPillar(55)).toBe(false);
  });

  it("reads ranking_score for the SCORE column", () => {
    expect(
      readRankingScore(
        stock({
          score: 55,
          ranking_score: 95,
          metrics: { stage_b_score: 80, ranking_score: 95 },
        })
      )
    ).toBe(95);
  });

  it("never shows Alpha/Conf/Trade pillars in the scan table", () => {
    const parts = readScanScoreParts(
      stock({
        ranking_score: 100,
        alpha_score: 100,
        confidence_score: 38,
        tradability_score: 62,
      })
    );
    expect(hasInformativePillarBreakdown(parts)).toBe(false);
    expect(displayPillars(parts)).toEqual([]);
    expect(parts.ranking).toBe(100);
  });

  it("falls back to score when ranking_score is absent", () => {
    expect(readScanScoreParts(stock({ score: 88, metrics: {} })).ranking).toBe(88);
  });
});
