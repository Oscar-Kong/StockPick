import { describe, expect, it } from "vitest";
import {
  analysisCacheKey,
  clearAnalysisCache,
  getAnalysisCache,
  setAnalysisCache,
} from "@/lib/analysisClientCache";
import { normalizeAnalysisTab } from "@/components/AnalysisTabNav";

describe("analysisClientCache", () => {
  it("stores and retrieves by symbol:bucket key", () => {
    clearAnalysisCache();
    const key = analysisCacheKey("aapl", "penny");
    setAnalysisCache(key, {
      base: { symbol: "AAPL", assigned_bucket: "penny", price: 1, score: 50 } as never,
      v2: null,
      freshness: { status: "cached" },
    });
    const hit = getAnalysisCache(key);
    expect(hit?.base.symbol).toBe("AAPL");
    clearAnalysisCache(key);
    expect(getAnalysisCache(key)).toBeNull();
  });
});

describe("normalizeAnalysisTab", () => {
  it("maps legacy nine-tab ids into five sections", () => {
    expect(normalizeAnalysisTab("score")).toBe("drivers");
    expect(normalizeAnalysisTab("valuation")).toBe("drivers");
    expect(normalizeAnalysisTab("similar")).toBe("evidence");
    expect(normalizeAnalysisTab("notes")).toBe("research");
    expect(normalizeAnalysisTab("overview")).toBe("overview");
  });
});
