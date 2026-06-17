import { describe, expect, it } from "vitest";
import {
  buildExposureCacheKey,
  buildRebalanceHoldings,
  checkOptimizationFeasibility,
  computeDrawdownSeries,
  parseSymbols,
} from "./portfolioUtils";

describe("portfolioUtils", () => {
  it("parseSymbols dedupes and uppercases", () => {
    expect(parseSymbols("aapl, msft, AAPL")).toEqual(["AAPL", "MSFT"]);
  });

  it("exposure cache key changes when lookback changes", () => {
    const base = { symbols: ["AAPL", "MSFT"], benchmark: "SPY" };
    const k1 = buildExposureCacheKey({ ...base, lookback: "1y" });
    const k2 = buildExposureCacheKey({ ...base, lookback: "2y" });
    expect(k1).not.toBe(k2);
  });

  it("exposure cache key changes when benchmark changes", () => {
    const base = { symbols: ["AAPL", "MSFT"], lookback: "1y" };
    const k1 = buildExposureCacheKey({ ...base, benchmark: "SPY" });
    const k2 = buildExposureCacheKey({ ...base, benchmark: "QQQ" });
    expect(k1).not.toBe(k2);
  });

  it("flags infeasible max-weight constraints", () => {
    const r = checkOptimizationFeasibility(4, 0.2, 0.05);
    expect(r.feasible).toBe(false);
    expect(r.reason).toMatch(/capacity/i);
  });

  it("passes feasible constraints", () => {
    const r = checkOptimizationFeasibility(4, 0.25, 0.05);
    expect(r.feasible).toBe(true);
  });

  it("buildRebalanceHoldings uses zero shares for missing symbols", () => {
    const summary = {
      as_of: "",
      total_value: 1000,
      invested_value: 900,
      cash: 100,
      cash_weight: 0.1,
      active_holdings_count: 1,
      positions: [{ symbol: "AAPL", shares: 5, price: 100, weight: 0.5 }],
      source: "ledger",
      data_source: "csv",
      data_source_label: "CSV",
      stale: false,
      warnings: [],
      disclaimer: "",
    };
    const holdings = buildRebalanceHoldings(["AAPL", "MSFT"], summary);
    expect(holdings).toHaveLength(2);
    expect(holdings.find((h) => h.symbol === "MSFT")?.shares).toBe(0);
  });

  it("computeDrawdownSeries peaks at zero drawdown", () => {
    const series = computeDrawdownSeries([
      { date: "2024-01-01", equity: 100 },
      { date: "2024-01-02", equity: 110 },
      { date: "2024-01-03", equity: 99 },
    ]);
    expect(series[0].drawdown_pct).toBe(0);
    expect(series[2].drawdown_pct).toBeCloseTo(-10, 1);
  });
});
