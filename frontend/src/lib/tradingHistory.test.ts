import { describe, expect, it } from "vitest";
import {
  ALL_MONTHS,
  ALL_YEARS,
  collectTradingPeriods,
  dedupeTradeRows,
  defaultYearFilter,
  filterTradesByPeriod,
  formatTradePrice,
  formatTradeQuantity,
  isRobinhoodMcpTrade,
  ledgerEntryDateParts,
  monthOptionsForYear,
  tradeSourceLabel,
} from "./tradingHistory";
import type { LedgerEntry } from "./types";

function trade(partial: Partial<LedgerEntry> & Pick<LedgerEntry, "id">): LedgerEntry {
  return {
    symbol: "AAPL",
    side: "buy",
    row_type: "buy",
    quantity: 1,
    price: 10,
    amount: -10,
    trans_code: "BUY",
    description: null,
    activity_date: "1/15/2025",
    process_date: null,
    executed_at: null,
    source: "csv",
    row_hash: `hash-${partial.id}`,
    locked: true,
    ...partial,
  };
}

describe("tradingHistory", () => {
  it("parses Robinhood-style activity dates", () => {
    expect(ledgerEntryDateParts({ activity_date: "6/29/2026" })).toEqual({ year: 2026, month: 6 });
    expect(ledgerEntryDateParts({ activity_date: "2025-03-01" })).toEqual({ year: 2025, month: 3 });
  });

  it("collects years and months from trade rows only", () => {
    const rows = [
      trade({ id: 1, activity_date: "1/10/2026" }),
      trade({ id: 2, activity_date: "3/5/2026", side: "sell", row_type: "sell" }),
      trade({ id: 3, activity_date: "2/1/2025" }),
      trade({ id: 4, row_type: "event", side: "event", activity_date: "1/1/2026" }),
    ];
    const { years, monthsByYear } = collectTradingPeriods(rows);
    expect(years).toEqual([2026, 2025]);
    expect(monthsByYear.get(2026)).toEqual([1, 3]);
    expect(monthsByYear.get(2025)).toEqual([2]);
  });

  it("filters by year and month", () => {
    const rows = [
      trade({ id: 1, activity_date: "1/10/2026" }),
      trade({ id: 2, activity_date: "3/5/2026", side: "sell", row_type: "sell" }),
      trade({ id: 3, activity_date: "3/12/2025" }),
    ];
    expect(filterTradesByPeriod(rows, 2026, ALL_MONTHS).map((r) => r.id)).toEqual([2, 1]);
    expect(filterTradesByPeriod(rows, 2026, 3).map((r) => r.id)).toEqual([2]);
    expect(filterTradesByPeriod(rows, ALL_YEARS, 3).map((r) => r.id)).toEqual([2, 3]);
  });

  it("defaults to the newest year with trades", () => {
    expect(defaultYearFilter([2026, 2025])).toBe(2026);
    expect(defaultYearFilter([])).toBe(ALL_YEARS);
  });

  it("lists month options for all years or a specific year", () => {
    const { monthsByYear } = collectTradingPeriods([
      trade({ id: 1, activity_date: "1/10/2026" }),
      trade({ id: 2, activity_date: "3/5/2025" }),
    ]);
    expect(monthOptionsForYear(monthsByYear, 2026)).toEqual([1]);
    expect(monthOptionsForYear(monthsByYear, ALL_YEARS)).toEqual([1, 3]);
  });

  it("labels Robinhood MCP fills", () => {
    const labels = { csv: "CSV", journal: "Journal", manual: "Manual", robinhood: "Robinhood" };
    expect(isRobinhoodMcpTrade(trade({ id: 9, trans_code: "MCP-BUY" }))).toBe(true);
    expect(isRobinhoodMcpTrade(trade({ id: 10, trans_code: "BUY" }))).toBe(false);
    expect(tradeSourceLabel("manual", "MCP-BUY", labels)).toBe("Robinhood");
    expect(tradeSourceLabel("csv", "BUY", labels)).toBe("CSV");
  });

  it("formats fractional share quantities compactly", () => {
    expect(formatTradeQuantity(42)).toBe("42");
    expect(formatTradeQuantity(0.424242)).toBe("0.4242");
    expect(formatTradePrice(1.9221)).toBe("$1.9221");
  });

  it("dedupes identical trade rows", () => {
    const rows = [
      trade({ id: 1, activity_date: "1/10/2026", row_hash: "dup" }),
      trade({ id: 2, activity_date: "1/10/2026", row_hash: "dup" }),
    ];
    expect(dedupeTradeRows(rows)).toHaveLength(1);
    expect(dedupeTradeRows(rows)[0]?.id).toBe(2);
  });
});
