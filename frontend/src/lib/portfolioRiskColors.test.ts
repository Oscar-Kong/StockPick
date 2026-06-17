import { describe, expect, it } from "vitest";
import {
  betaSeverity,
  betaTextClass,
  concentrationStats,
  correlationCellClass,
  effectiveBetsSeverity,
} from "./portfolioRiskColors";

describe("portfolioRiskColors", () => {
  it("classifies beta severity", () => {
    expect(betaSeverity(0.7)).toBe("low");
    expect(betaSeverity(1.0)).toBe("moderate");
    expect(betaSeverity(1.25)).toBe("elevated");
    expect(betaSeverity(1.5)).toBe("high");
  });

  it("returns distinct text classes for beta levels", () => {
    expect(betaTextClass(0.7)).toContain("sky");
    expect(betaTextClass(1.4)).toContain("red");
  });

  it("computes HHI and effective bets", () => {
    const equal = concentrationStats([0.25, 0.25, 0.25, 0.25]);
    expect(equal.effectiveBets).toBeCloseTo(4, 1);
    const concentrated = concentrationStats([0.7, 0.15, 0.15]);
    expect(concentrated.effectiveBets).toBeLessThan(3);
  });

  it("colors correlation cells by magnitude", () => {
    expect(correlationCellClass(0.9, false)).toContain("red");
    expect(correlationCellClass(0.15, false)).toContain("emerald");
    expect(correlationCellClass(0.3, false)).toContain("sky");
    expect(correlationCellClass(1, true)).toContain("zinc");
  });

  it("rates effective bets diversification", () => {
    expect(effectiveBetsSeverity(10)).toBe("low");
    expect(effectiveBetsSeverity(2)).toBe("high");
  });
});
