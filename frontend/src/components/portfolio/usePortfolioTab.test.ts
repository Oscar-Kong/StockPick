import { describe, expect, it } from "vitest";
import { parsePortfolioTab, parseResearchPanel } from "./usePortfolioTab";

describe("usePortfolioTab parsers", () => {
  it("defaults invalid tab to today", () => {
    expect(parsePortfolioTab(null)).toBe("today");
    expect(parsePortfolioTab("bogus")).toBe("today");
  });

  it("parses plan, research, and activity tabs", () => {
    expect(parsePortfolioTab("plan")).toBe("plan");
    expect(parsePortfolioTab("research")).toBe("research");
    expect(parsePortfolioTab("activity")).toBe("activity");
  });

  it("maps legacy tools query to research panels", () => {
    expect(parseResearchPanel("rebalance")).toBe("optimize");
    expect(parseResearchPanel("risk")).toBe("exposure");
    expect(parseResearchPanel("backtest")).toBe("backtest");
    expect(parseResearchPanel("advanced")).toBe("allocation");
  });

  it("parses modern research panel names", () => {
    expect(parseResearchPanel("optimize")).toBe("optimize");
    expect(parseResearchPanel("exposure")).toBe("exposure");
    expect(parseResearchPanel("allocation")).toBe("allocation");
  });
});
