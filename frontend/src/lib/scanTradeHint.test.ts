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
        },
      })
    );
    expect(hint.buyPct).toBe(62);
    expect(hint.recommendation).toBe("buy");
  });

  it("derives fallback for legacy cached rows", () => {
    const hint = deriveScanTradeHint(stock({ score: 82 }));
    expect(hint.buyPct + hint.waitPct).toBe(100);
    expect(hint.buyPct).toBeGreaterThan(hint.waitPct);
  });
});
