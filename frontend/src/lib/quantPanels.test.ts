import { describe, expect, it } from "vitest";
import { fmtNum, fmtPct } from "../components/AsyncSection";
import type { SymbolDiagnosticsResponse } from "./types";

describe("quant panel formatters", () => {
  it("fmtPct handles null and values", () => {
    expect(fmtPct(null)).toBe("—");
    expect(fmtPct(0.152)).toBe("15.2%");
  });

  it("fmtNum handles null", () => {
    expect(fmtNum(undefined)).toBe("—");
    expect(fmtNum(1.2, 2)).toBe("1.20");
  });
});

describe("SymbolDiagnosticsResponse shape", () => {
  it("accepts insufficient data payload", () => {
    const payload: SymbolDiagnosticsResponse = {
      symbol: "TEST",
      lookback: 252,
      price_bars: 10,
      return_bars: 0,
      observations: 0,
      data_source: "none",
      sufficient_data: false,
      mean: null,
      annualized_volatility: null,
      skewness: null,
      excess_kurtosis: null,
      jarque_bera: { available: false },
      adf: { available: false },
      autocorrelation: { lag1: null },
      interpretation: "insufficient data",
      notes: ["Need more bars"],
    };
    expect(payload.sufficient_data).toBe(false);
    expect(payload.interpretation).toBe("insufficient data");
  });
});
