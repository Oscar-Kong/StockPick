import { describe, expect, it } from "vitest";
import { deriveScanTradeHint, getScanTradeHint } from "./scanTradeHint";
import type { StockResult } from "./types";

function stock(partial: Partial<StockResult> = {}): StockResult {
  return {
    symbol: "TEST",
    price: 10,
    score: 70,
    signals: [],
    risk_level: "medium",
    summary: "",
    bucket: "penny",
    metrics: {},
    valuation_warnings: [],
    earnings_soon: false,
    ...partial,
  };
}

describe("scanTradeHint", () => {
  it("reads server metrics when present", () => {
    const hint = getScanTradeHint(
      stock({
        metrics: {
          recommendation: "buy",
          buy_pct: 62,
          wait_pct: 38,
          trade_hint_reason: "Score 70 supports entry",
          stability_score: 78,
          stability_classification: "normal",
          entry_risk_score: 64,
          entry_risk_classification: "extended",
          entry_risk_source: "daily_ohlcv_proxy",
        },
      })
    );
    expect(hint.buyPct).toBe(62);
    expect(hint.recommendation).toBe("buy");
    expect(hint.stability).toEqual({ score: 78, classification: "normal" });
    expect(hint.entryRisk).toEqual({
      score: 64,
      classification: "extended",
      source: "daily_ohlcv_proxy",
    });
  });

  it("derives fallback for legacy cached rows", () => {
    const hint = deriveScanTradeHint(stock({ score: 82 }));
    expect(hint.buyPct + hint.waitPct).toBe(100);
    expect(hint.buyPct).toBeGreaterThan(hint.waitPct);
  });

  it("applies stability and entry gates when server hint fields are partial", () => {
    const hint = deriveScanTradeHint(
      stock({
        score: 90,
        metrics: {
          stability_score: 80,
          stability_classification: "stable",
          entry_risk_score: 82,
          entry_risk_classification: "no_chase",
          entry_risk_source: "daily_ohlcv_proxy",
        },
      })
    );

    expect(hint.recommendation).toBe("watch");
    expect(hint.waitPct).toBeGreaterThan(hint.buyPct);
  });
});
