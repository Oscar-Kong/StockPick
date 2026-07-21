import { describe, expect, it } from "vitest";
import { getCockpitStatus, mergeHoldingsWithDecisionItems } from "@/lib/dailyDecisionUtils";
import type { DailyDashboardResponse, PortfolioDecisionItem } from "@/lib/types";

function base(overrides: Partial<DailyDashboardResponse> = {}): DailyDashboardResponse {
  return {
    portfolio_value: 2105.82,
    cash: 2105.82,
    data_source: "manual",
    data_source_label: "Manual",
    holdings: [],
    top_penny_opportunities: [],
    portfolio_warnings: [],
    disclaimer: "",
    ...overrides,
  };
}

function decisionItem(symbol: string, overrides: Partial<PortfolioDecisionItem> = {}): PortfolioDecisionItem {
  return {
    symbol,
    bucket: "penny",
    price: 1,
    price_available: true,
    shares: 1,
    avg_cost: 1,
    market_value: 1,
    pl_pct: 0,
    current_weight: 0,
    target_weight: 0,
    buy_pct: 0,
    keep_pct: 100,
    sell_pct: 0,
    decision: "review",
    score: 50,
    risk_index: 50,
    suggested_dollar_action: 0,
    reasons: [],
    risk_flags: [],
    ...overrides,
  };
}

describe("mergeHoldingsWithDecisionItems", () => {
  it("drops orphan decision symbols not in open holdings (stale ZZZZ healthcheck)", () => {
    const merged = mergeHoldingsWithDecisionItems(
      [],
      [decisionItem("ZZZZ")]
    );
    expect(merged).toEqual([]);
  });

  it("keeps decision rows that match open holdings", () => {
    const merged = mergeHoldingsWithDecisionItems(
      [{ symbol: "AMC", shares: 10, avg_cost: 2, bucket: "penny" }],
      [decisionItem("AMC", { shares: 10 }), decisionItem("ZZZZ")]
    );
    expect(merged.map((i) => i.symbol)).toEqual(["AMC"]);
  });
});

describe("getCockpitStatus", () => {
  it("shows import_needed when there are no holdings and no MCP sync", () => {
    expect(getCockpitStatus(base())).toBe("import_needed");
  });

  it("does not show import_needed for cash-only Robinhood MCP sync", () => {
    expect(
      getCockpitStatus(
        base({
          data_source: "robinhood_mcp",
          data_source_label: "Robinhood (live MCP)",
          robinhood_mcp_authenticated: true,
          robinhood_mcp_enabled: true,
          freshness: {
            overall_status: "missing",
            items: [],
            refresh_recommended: true,
            refresh_in_progress: false,
          },
        })
      )
    ).toBe("ready");
  });

  it("does not show stale for cash-only Robinhood MCP even when freshness is stale", () => {
    expect(
      getCockpitStatus(
        base({
          data_source: "robinhood_mcp",
          data_source_label: "Robinhood (live MCP)",
          robinhood_mcp_authenticated: true,
          robinhood_mcp_enabled: true,
          decision_stale_warning: "Decision is based on older data. Refresh before acting.",
          freshness: {
            overall_status: "stale",
            items: [],
            refresh_recommended: true,
            refresh_in_progress: false,
          },
        })
      )
    ).toBe("ready");
  });
});
