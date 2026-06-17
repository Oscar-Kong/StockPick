import { describe, expect, it } from "vitest";
import { buildPriceChartSeries, CHART_RANGE_BARS, periodChangePct } from "@/lib/chartSeries";

function makeOhlc(count: number, start = "2026-01-01") {
  const rows = [];
  const d = new Date(start);
  for (let i = 0; i < count; i += 1) {
    const date = new Date(d);
    date.setDate(d.getDate() + i);
    rows.push({ date: date.toISOString().slice(0, 10), close: 10 + i * 0.1 });
  }
  return rows;
}

describe("chartSeries", () => {
  it("computes MA200 before trimming display range", () => {
    const ohlc = makeOhlc(260);
    const trimmed = buildPriceChartSeries(ohlc, CHART_RANGE_BARS["1M"]);
    expect(trimmed.length).toBe(21);
    const last = trimmed[trimmed.length - 1];
    expect(last.ma200).not.toBeNull();
  });

  it("reports period change for selected window", () => {
    const ohlc = makeOhlc(30);
    const rows = buildPriceChartSeries(ohlc, 10);
    const change = periodChangePct(rows);
    expect(change).not.toBeNull();
    expect(change!).toBeGreaterThan(0);
  });

  it("preserves fullDate for tooltip display", () => {
    const ohlc = [{ date: "2026-06-08", close: 12.5 }];
    const rows = buildPriceChartSeries(ohlc);
    expect(rows[0].fullDate).toBe("2026-06-08");
  });
});
