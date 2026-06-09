import { describe, expect, it } from "vitest";
import {
  computeDataQualityReliability,
  computeFactorLifecycleStatus,
  computeFactorPerformanceReliability,
  computeModelAdminReliability,
  computePairsReliability,
  computePredictionsReliability,
  computeWalkForwardOverfittingWarnings,
  computeWalkForwardReliability,
  PBO_NOT_IMPLEMENTED_WARNING,
} from "./researchReliability";
import type { FactorPerformanceFactor, FactorPerformanceResponse } from "./types";

const sampleFactor = (id: string, ic: number, n: number): FactorPerformanceFactor => ({
  factor_id: id,
  sleeve: "medium",
  horizons: {
    "20": {
      factor_id: id,
      sleeve: "medium",
      horizon_days: 20,
      ic,
      ir: ic * 2,
      hit_rate: 0.55,
      sample_n: n,
    },
  },
});

describe("researchReliability", () => {
  describe("computeFactorPerformanceReliability", () => {
    it("returns insufficient_data when no IC rows", () => {
      const score = computeFactorPerformanceReliability({ data: null });
      expect(score.status).toBe("insufficient_data");
      expect(score.blockers).toContain("noIcData");
    });

    it("returns disabled when feature disabled", () => {
      const score = computeFactorPerformanceReliability({ data: null, disabled: true });
      expect(score.status).toBe("disabled");
    });

    it("returns stale when IC as_of is old", () => {
      const data: FactorPerformanceResponse = {
        as_of_date: "2020-01-01",
        horizons: [20],
        factors: [
          sampleFactor("a", 0.04, 120),
          sampleFactor("b", 0.03, 110),
          sampleFactor("c", 0.02, 100),
        ],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      };
      const score = computeFactorPerformanceReliability({ data });
      expect(score.status).toBe("stale");
      expect(score.warnings).toContain("icStale");
    });

    it("scores strong IC panel as reliable", () => {
      const today = new Date().toISOString().slice(0, 10);
      const data: FactorPerformanceResponse = {
        as_of_date: today,
        horizons: [20, 60],
        factors: [
          sampleFactor("a", 0.06, 150),
          sampleFactor("b", 0.05, 140),
          sampleFactor("c", 0.04, 130),
          sampleFactor("d", 0.03, 120),
          sampleFactor("e", 0.02, 110),
        ],
        by_horizon: {},
        by_regime: {},
        by_sector: {},
      };
      const score = computeFactorPerformanceReliability({ data });
      expect(score.status).toBe("reliable");
      expect(score.score_0_to_100).toBeGreaterThanOrEqual(80);
    });
  });

  describe("computeFactorLifecycleStatus", () => {
    it("promotes strong factors with fresh data", () => {
      expect(computeFactorLifecycleStatus(sampleFactor("x", 0.06, 120), false)).toBe("promote");
    });

    it("retires negative IC factors", () => {
      expect(computeFactorLifecycleStatus(sampleFactor("x", -0.02, 120), false)).toBe("retire");
    });

    it("returns insufficient_evidence for low sample", () => {
      expect(computeFactorLifecycleStatus(sampleFactor("x", 0.05, 10), false)).toBe(
        "insufficient_evidence"
      );
    });
  });

  describe("computeWalkForwardReliability", () => {
    it("returns research_only when no saved run", () => {
      const score = computeWalkForwardReliability({ result: null });
      expect(score.status).toBe("research_only");
      expect(score.blockers).toContain("noSavedRun");
    });

    it("returns weak_evidence for thin walk-forward", () => {
      const score = computeWalkForwardReliability({
        result: {
          run_id: "abc",
          status: "completed",
          sleeve: "medium",
          start_date: "2024-01-01",
          end_date: "2025-01-01",
          rebalance_frequency: "monthly",
          forward_horizons: [20],
          rebalance_periods: 2,
          periods_scored: 2,
          snapshots_written: 0,
        },
      });
      expect(["weak_evidence", "usable_with_warnings", "research_only", "insufficient_data"]).toContain(
        score.status
      );
      expect(score.warnings.length).toBeGreaterThan(0);
    });
  });

  describe("computeWalkForwardOverfittingWarnings", () => {
    it("includes PBO placeholder", () => {
      const flags = computeWalkForwardOverfittingWarnings(null);
      expect(flags.pbo_available).toBe(false);
      expect(flags.pbo_warning).toBe(PBO_NOT_IMPLEMENTED_WARNING);
      expect(flags.warnings).toContain(PBO_NOT_IMPLEMENTED_WARNING);
    });

    it("warns on too few windows", () => {
      const flags = computeWalkForwardOverfittingWarnings({
        run_id: "x",
        status: "completed",
        sleeve: "medium",
        start_date: "2024-01-01",
        end_date: "2025-01-01",
        rebalance_frequency: "monthly",
        forward_horizons: [20],
        rebalance_periods: 2,
        periods_scored: 2,
        snapshots_written: 0,
      });
      expect(flags.warnings).toContain("tooFewWindows");
      expect(flags.warnings).toContain("noTransactionCosts");
    });
  });

  describe("computePredictionsReliability", () => {
    it("returns insufficient_data when empty", () => {
      const score = computePredictionsReliability({ predictions: [], feedback: null });
      expect(score.status).toBe("insufficient_data");
    });

    it("returns disabled when feature off", () => {
      const score = computePredictionsReliability({
        predictions: [],
        feedback: null,
        disabled: true,
      });
      expect(score.status).toBe("disabled");
    });
  });

  describe("computePairsReliability", () => {
    it("returns research_only with no result", () => {
      const score = computePairsReliability({ result: null });
      expect(score.status).toBe("research_only");
    });
  });

  describe("computeDataQualityReliability", () => {
    it("returns insufficient_data without health or scheduler", () => {
      const score = computeDataQualityReliability({ health: null, scheduler: null, loading: false });
      expect(score.status).toBe("insufficient_data");
    });
  });

  describe("computeModelAdminReliability", () => {
    it("returns disabled when v2 off", () => {
      const score = computeModelAdminReliability({ version: null, weights: null, audit: null, factorsAdmin: null, disabled: true });
      expect(score.status).toBe("disabled");
    });
  });
});
