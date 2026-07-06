import { describe, expect, it } from "vitest";
import type { AnalyzeSymbolResponse, V2ScoreResponse } from "./types";
import {
  factorsToSignals,
  hasV2Factors,
  isV2ScoreResponse,
  parseV2FetchError,
  resolveAnalysisDisplay,
  scoreSourcesDiffer,
} from "./v2Score";

const legacyBase: AnalyzeSymbolResponse = {
  symbol: "TEST",
  assigned_bucket: "penny",
  price: 100,
  score: 72,
  risk_level: "medium",
  summary: "Legacy summary",
  signals: [{ name: "Legacy signal", value: 70, weight: 1, contribution: 70, description: "" }],
  metrics: {},
  valuation_warnings: [],
  earnings_date: null,
  days_until_earnings: null,
  earnings_soon: false,
  data_quality_score: 80,
  reconcile: {},
  technicals: {},
  bucket_fit: { scores: {}, best_bucket: "penny" },
  alerts: [],
  ohlc: [],
  fundamentals: {},
};

const v2Base: V2ScoreResponse = {
  symbol: "TEST",
  sleeve: "penny",
  score: 68,
  summary: "Engine summary",
  risk_level: "medium",
  factors: [
    {
      factor_id: "momentum",
      display_name: "Momentum",
      norm_score: 65,
      weight: 0.4,
      contribution: 26,
      description: "test",
    },
  ],
  attribution: {
    raw_score: 70,
    regime_mult: 1,
    sector_tilt: 0,
    dq_multiplier: 1,
    score_after_regime: 70,
    score_after_dq: 68,
    risk_deduction: 2,
    final_score: 68,
  },
  risk: { risk_score: 40, deduction_pts: 2, items: [] },
  recommendation: {
    recommendation: "watch",
    confidence: 55,
    time_horizon_days: 20,
    expected_return_pct: 3,
    expected_downside_pct: 5,
    pillars: { alpha_score: 60, valuation_score: 55, catalyst_score: 50 },
    data_confidence: { data_confidence: 75, issues: [] },
    gates: [],
    bull_case: "test",
    bear_case: "test",
  },
};

describe("v2Score helpers", () => {
  it("isV2ScoreResponse validates shape", () => {
    expect(isV2ScoreResponse(v2Base)).toBe(true);
    expect(isV2ScoreResponse(null)).toBe(false);
    expect(isV2ScoreResponse({ symbol: "X", score: 1 })).toBe(false);
  });

  it("resolveAnalysisDisplay prefers v2 when present", () => {
    const display = resolveAnalysisDisplay(legacyBase, v2Base);
    expect(display.scoreSource).toBe("scoring_engine_v2");
    expect(display.score).toBe(68);
    expect(display.hasV2).toBe(true);
    expect(display.legacyScore).toBe(72);
    expect(display.signals[0].name).toBe("Momentum");
  });

  it("resolveAnalysisDisplay falls back to legacy without v2", () => {
    const display = resolveAnalysisDisplay(legacyBase, null);
    expect(display.scoreSource).toBe("legacy_screener");
    expect(display.score).toBe(72);
    expect(display.hasV2).toBe(false);
  });

  it("handles missing optional v2 fields", () => {
    const partial = { ...v2Base, recommendation: null, valuation: null, factors: [] };
    expect(hasV2Factors(partial)).toBe(false);
    const display = resolveAnalysisDisplay(legacyBase, partial);
    expect(display.signals).toEqual(legacyBase.signals);
  });

  it("factorsToSignals maps contributions", () => {
    const signals = factorsToSignals(v2Base);
    expect(signals).toHaveLength(1);
    expect(signals[0].contribution).toBe(26);
  });

  it("scoreSourcesDiffer detects mismatch", () => {
    const display = resolveAnalysisDisplay(legacyBase, v2Base);
    expect(scoreSourcesDiffer(display)).toBe(true);
  });

  it("parseV2FetchError classifies API errors", () => {
    expect(parseV2FetchError(new Error('503 SCORE_ENGINE_V2_ENABLED is false'))).toBe("disabled");
    expect(parseV2FetchError(new Error("404 not found"))).toBe("not_found");
    expect(parseV2FetchError(new Error("network"))).toBe("error");
  });
});
