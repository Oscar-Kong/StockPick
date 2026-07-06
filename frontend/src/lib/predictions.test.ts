import { describe, expect, it } from "vitest";
import {
  arePredictionOutcomesStale,
  countUnresolvedPredictions,
  formatScore,
  isPredictionResolved,
  predictionDisplayScore,
  predictionReturnPct,
} from "./predictions";
import type { FeedbackSummaryResponse, PredictionSnapshotItem } from "./types";

const snapshot = (overrides: Partial<PredictionSnapshotItem> = {}): PredictionSnapshotItem => ({
  id: 1,
  symbol: "AAPL",
  sleeve: "penny",
  source: "v2_score",
  created_at: new Date().toISOString(),
  outcome: null,
  ...overrides,
});

describe("prediction helpers", () => {
  it("isPredictionResolved uses outcome object", () => {
    expect(isPredictionResolved(snapshot())).toBe(false);
    expect(isPredictionResolved(snapshot({ outcome: { return_60d: 2.1 } }))).toBe(true);
  });

  it("predictionDisplayScore prefers alpha_score", () => {
    expect(predictionDisplayScore(snapshot({ alpha_score: 72, confidence: 40 }))).toBe(72);
    expect(predictionDisplayScore(snapshot({ confidence: 40 }))).toBe(40);
    expect(predictionDisplayScore(snapshot())).toBeNull();
  });

  it("predictionReturnPct reads outcome horizons", () => {
    expect(predictionReturnPct(snapshot({ outcome: { return_60d: 3.5 } }), 60)).toBe(3.5);
    expect(predictionReturnPct(snapshot(), 60)).toBeNull();
  });

  it("formatScore handles null", () => {
    expect(formatScore(null)).toBe("—");
    expect(formatScore(50.12)).toBe("50.1");
  });

  it("countUnresolvedPredictions counts open snapshots", () => {
    expect(
      countUnresolvedPredictions([
        snapshot(),
        snapshot({ id: 2, outcome: { return_60d: 1 } }),
      ])
    ).toBe(1);
  });

  it("arePredictionOutcomesStale when old unresolved snapshots exist", () => {
    const old = new Date(Date.now() - 10 * 24 * 3600 * 1000).toISOString();
    const feedback: FeedbackSummaryResponse = {
      outcomes_count: 0,
      snapshots_count: 5,
      recent_outcomes: [],
      recent_snapshots: [],
    };
    expect(arePredictionOutcomesStale([snapshot({ created_at: old })], feedback)).toBe(true);
    expect(arePredictionOutcomesStale([snapshot({ outcome: { return_60d: 1 } })], feedback)).toBe(
      false
    );
  });
});
