import { describe, expect, it } from "vitest";
import {
  displayPillars,
  hasInformativePillarBreakdown,
  isNeutralPillar,
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
    expect(isNeutralPillar(49)).toBe(true);
    expect(isNeutralPillar(51)).toBe(true);
    expect(isNeutralPillar(55)).toBe(false);
  });

  it("hides breakdown when confidence and tradability are neutral", () => {
    const parts = readScanScoreParts(
      stock({
        ranking_score: 68,
        alpha_score: 80,
        confidence_score: 50,
        tradability_score: 50,
      })
    );
    expect(hasInformativePillarBreakdown(parts)).toBe(false);
    expect(displayPillars(parts)).toEqual([{ key: "alpha", metricKey: "alpha_score", value: 80 }]);
  });

  it("shows breakdown when confidence differs from neutral", () => {
    const parts = readScanScoreParts(
      stock({
        ranking_score: 68,
        confidence_score: 62,
        tradability_score: 50,
      })
    );
    expect(hasInformativePillarBreakdown(parts)).toBe(true);
    expect(displayPillars(parts).map((p) => p.key)).toContain("confidence");
  });

  it("reads ranking from metrics fallback", () => {
    const parts = readScanScoreParts(
      stock({
        score: 55,
        metrics: { ranking_score: 61, confidence_score: 50, tradability_score: 50 },
      })
    );
    expect(parts.ranking).toBe(61);
    expect(hasInformativePillarBreakdown(parts)).toBe(false);
  });
});
