import { describe, expect, it } from "vitest";
import { normalizeLastRunSummary, normalizeQuantLabEvidence } from "@/lib/quantLabLastRun";

describe("quantLabLastRun", () => {
  it("normalizes unavailable summary", () => {
    const s = normalizeLastRunSummary(
      { available: false, reason: "No saved run found", trust_indicator: "no_saved_run" },
      "pairs"
    );
    expect(s.available).toBe(false);
    expect(s.trust_indicator).toBe("no_saved_run");
  });

  it("normalizes available summary with metrics", () => {
    const s = normalizeLastRunSummary(
      {
        id: "walk_forward",
        available: true,
        generated_at: "2026-01-15T12:00:00",
        sample_size: 12,
        main_metric: { label: "Mean rank IC", value: "0.042" },
        stale: true,
        stale_reason: "Old run",
        warnings: ["Low periods"],
        trust_indicator: "stale",
        research_only: true,
      },
      "walk_forward"
    );
    expect(s.main_metric?.value).toBe("0.042");
    expect(s.stale).toBe(true);
    expect(s.trust_indicator).toBe("stale");
  });

  it("normalizes full evidence response", () => {
    const e = normalizeQuantLabEvidence({
      sleeve: "penny",
      generated_at: "2026-06-05",
      factor_ic: { available: true, id: "factor_ic", stale: false, warnings: [], trust_indicator: "fresh", research_only: false },
      walk_forward: { available: false, id: "walk_forward", stale: false, warnings: [], trust_indicator: "no_saved_run", research_only: true },
      predictions: { available: false, id: "predictions", stale: false, warnings: [], trust_indicator: "no_saved_run", research_only: false },
      pairs: { available: false, id: "pairs", stale: false, warnings: [], trust_indicator: "no_saved_run", research_only: true },
      jobs: { available: true, id: "jobs", stale: false, warnings: [], trust_indicator: "fresh", research_only: false },
    });
    expect(e.factor_ic.available).toBe(true);
    expect(e.pairs.available).toBe(false);
  });
});
