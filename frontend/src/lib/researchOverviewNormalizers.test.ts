import { describe, expect, it } from "vitest";
import { normalizeResearchOverviewResponse } from "./researchOverviewNormalizers";

describe("researchOverviewNormalizers", () => {
  it("returns safe defaults for invalid payload", () => {
    const out = normalizeResearchOverviewResponse(null);
    expect(out.sleeve).toBe("penny");
    expect(out.findings).toEqual([]);
    expect(out.maintenance_actions).toEqual([]);
  });

  it("normalizes partial overview payload", () => {
    const out = normalizeResearchOverviewResponse({
      sleeve: "penny",
      research_confidence_score: 55,
      findings: [{ finding_id: "f1", title: "Test" }],
    });
    expect(out.sleeve).toBe("penny");
    expect(out.research_confidence_score).toBe(55);
    expect(out.findings).toHaveLength(1);
    expect(out.findings[0]?.title).toBe("Test");
  });
});
