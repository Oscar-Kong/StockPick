import { describe, expect, it } from "vitest";
import {
  formatWalkForwardHorizonStats,
  parseSymbolList,
  validateWalkForwardDates,
  PAIRS_MAX_SYMBOLS,
} from "./quantLabFormatters";

describe("quantLabFormatters", () => {
  it("parseSymbolList dedupes and uppercases", () => {
    expect(parseSymbolList("aapl, msft, AAPL")).toEqual(["AAPL", "MSFT"]);
  });

  it("validateWalkForwardDates rejects invalid range", () => {
    expect(validateWalkForwardDates("2026-01-01", "2025-01-01")).toBe("start_after_end");
    expect(validateWalkForwardDates("bad", "2025-01-01")).toBe("invalid_date");
    expect(validateWalkForwardDates("2024-01-01", "2026-01-01")).toBeNull();
  });

  it("formatWalkForwardHorizonStats renders structured stats", () => {
    expect(formatWalkForwardHorizonStats({ periods: 0, sufficient: false })).toContain("0 periods");
    expect(formatWalkForwardHorizonStats(null)).toBe("—");
  });

  it("PAIRS_MAX_SYMBOLS is reasonable", () => {
    expect(PAIRS_MAX_SYMBOLS).toBeGreaterThanOrEqual(2);
  });
});
