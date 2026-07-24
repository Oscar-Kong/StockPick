import { describe, expect, it } from "vitest";
import {
  SCAN_SCORE_STRONG_MIN,
  SCAN_SCORE_WATCH_MIN,
  scoreBandForStock,
  scorePercentileInScan,
} from "./scanScoreBand";
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

describe("scanScoreBand", () => {
  it("uses recalibrated thresholds", () => {
    expect(SCAN_SCORE_STRONG_MIN).toBe(70);
    expect(SCAN_SCORE_WATCH_MIN).toBe(65);
  });

  it("maps scores to strong/watch/skip", () => {
    expect(scoreBandForStock(stock({ ranking_score: 72 }))).toBe("strong");
    expect(scoreBandForStock(stock({ ranking_score: 67 }))).toBe("watch");
    expect(scoreBandForStock(stock({ ranking_score: 60 }))).toBe("skip");
  });

  it("marks partial-data fallback separately even at 100", () => {
    expect(
      scoreBandForStock(
        stock({
          ranking_score: 100,
          metrics: { provider_limited_partial_data: true },
        })
      )
    ).toBe("fallback");
  });

  it("computes percentile within the scan", () => {
    expect(scorePercentileInScan(72, [50, 60, 72, 80])).toBe(63);
    expect(scorePercentileInScan(80, [50, 60, 72, 80])).toBe(88);
  });
});
