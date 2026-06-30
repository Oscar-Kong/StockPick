import { describe, expect, it } from "vitest";
import {
  buildEquityChartSummaryLines,
  buildPriceChartSummaryLines,
  maxDrawdownFromSeries,
  periodReturnPct,
} from "./chartSummary";

describe("chartSummary", () => {
  it("computes period return", () => {
    expect(periodReturnPct(100, 108)).toBeCloseTo(8, 5);
    expect(periodReturnPct(100, 92)).toBeCloseTo(-8, 5);
  });

  it("builds price chart summary lines", () => {
    const lines = buildPriceChartSummaryLines({
      periodLabel: "3M",
      startPrice: 100,
      endPrice: 108,
      periodChangePct: 8,
      latestDate: "2026-06-30",
    });
    expect(lines).toHaveLength(5);
    expect(lines[0]?.value).toBe("3M");
    expect(lines[lines.length - 1]?.value).toBe("2026-06-30");
  });

  it("builds equity summary with benchmark", () => {
    const lines = buildEquityChartSummaryLines({
      periodLabel: "1y",
      startEquity: 10000,
      endEquity: 11000,
      benchmarkStart: 10000,
      benchmarkEnd: 10500,
      maxDrawdownPct: -5.2,
      latestDate: "2026-06-29",
    });
    expect(lines.some((l) => l.label === "Benchmark change")).toBe(true);
    expect(lines.some((l) => l.label === "Maximum drawdown" && l.value === "-5.2%")).toBe(true);
  });

  it("computes max drawdown from series", () => {
    expect(maxDrawdownFromSeries([100, 110, 99, 105])).toBeCloseTo(-10, 5);
  });
});
