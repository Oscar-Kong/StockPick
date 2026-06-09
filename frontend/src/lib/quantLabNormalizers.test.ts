import { describe, expect, it } from "vitest";
import {
  factorPerformanceRows,
  normalizeFactorPerformanceResponse,
  normalizeFeedbackSummaryResponse,
  normalizePredictionsListResponse,
  normalizeSchedulerStatusResponse,
  normalizeV2AuditResponse,
} from "./quantLabNormalizers";

describe("quantLabNormalizers", () => {
  it("normalizeFactorPerformanceResponse handles null and empty factors", () => {
    const empty = normalizeFactorPerformanceResponse(null);
    expect(empty.factors).toEqual([]);
    expect(empty.as_of_date).toBeNull();

    const withBad = normalizeFactorPerformanceResponse({
      as_of_date: "2026-06-09",
      factors: [{ factor_id: "x", horizons: {} }, { horizons: { "20": { ic: 0.1, sample_n: 10 } } }],
    });
    expect(factorPerformanceRows(withBad)).toHaveLength(0);
  });

  it("normalizePredictionsListResponse maps alpha_score and outcome", () => {
    const res = normalizePredictionsListResponse({
      predictions: [
        {
          id: 1,
          symbol: "AAPL",
          sleeve: "medium",
          source: "v2",
          created_at: "2026-01-01T00:00:00Z",
          alpha_score: 72,
          outcome: { return_60d: 3.2 },
        },
        { symbol: "BAD" },
      ],
    });
    expect(res.predictions).toHaveLength(1);
    expect(res.predictions[0].alpha_score).toBe(72);
    expect(res.predictions[0].outcome?.return_60d).toBe(3.2);
  });

  it("normalizeFeedbackSummaryResponse defaults counts", () => {
    const res = normalizeFeedbackSummaryResponse({});
    expect(res.outcomes_count).toBe(0);
    expect(res.recent_outcomes).toEqual([]);
  });

  it("normalizeSchedulerStatusResponse defaults recent_jobs", () => {
    const res = normalizeSchedulerStatusResponse({ enabled: true });
    expect(res.recent_jobs).toEqual([]);
  });

  it("normalizeV2AuditResponse defaults events", () => {
    expect(normalizeV2AuditResponse(undefined).events).toEqual([]);
  });
});
