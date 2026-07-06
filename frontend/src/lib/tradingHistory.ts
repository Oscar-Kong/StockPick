import { compareLedgerRowsDesc, parseLedgerActivityDate } from "@/lib/datetime";
import type { LedgerEntry } from "@/lib/types";

export const ALL_YEARS = "all" as const;
export const ALL_MONTHS = "all" as const;

export type YearFilter = typeof ALL_YEARS | number;
export type MonthFilter = typeof ALL_MONTHS | number;

type DateParts = { year: number; month: number };

export function ledgerEntryDateParts(entry: {
  activity_date?: string | null;
  process_date?: string | null;
  executed_at?: string | null;
}): DateParts | null {
  for (const field of [entry.executed_at, entry.activity_date, entry.process_date]) {
    const t = parseLedgerActivityDate(field);
    if (!Number.isNaN(t)) {
      const d = new Date(t);
      return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1 };
    }
  }
  return null;
}

export function isTradeRow(row: LedgerEntry): boolean {
  return row.row_type === "buy" || row.row_type === "sell";
}

export function isRobinhoodMcpTrade(row: LedgerEntry): boolean {
  return (row.trans_code ?? "").toUpperCase().startsWith("MCP-");
}

export function collectTradingPeriods(rows: LedgerEntry[]): {
  years: number[];
  monthsByYear: Map<number, number[]>;
} {
  const monthsByYear = new Map<number, Set<number>>();
  for (const row of rows) {
    if (!isTradeRow(row)) continue;
    const parts = ledgerEntryDateParts(row);
    if (!parts) continue;
    const set = monthsByYear.get(parts.year) ?? new Set<number>();
    set.add(parts.month);
    monthsByYear.set(parts.year, set);
  }
  const years = [...monthsByYear.keys()].sort((a, b) => b - a);
  const normalized = new Map<number, number[]>();
  for (const [y, months] of monthsByYear) {
    normalized.set(y, [...months].sort((a, b) => a - b));
  }
  return { years, monthsByYear: normalized };
}

export function filterTradesByPeriod(
  rows: LedgerEntry[],
  year: YearFilter,
  month: MonthFilter,
): LedgerEntry[] {
  const filtered = rows.filter((row) => {
    if (!isTradeRow(row)) return false;
    const parts = ledgerEntryDateParts(row);
    if (!parts) return false;
    if (year !== ALL_YEARS && parts.year !== year) return false;
    if (month !== ALL_MONTHS && parts.month !== month) return false;
    return true;
  });
  return [...filtered].sort(compareLedgerRowsDesc);
}

export function defaultYearFilter(years: number[]): YearFilter {
  return years[0] ?? ALL_YEARS;
}

export function monthOptionsForYear(
  monthsByYear: Map<number, number[]>,
  year: YearFilter,
): number[] {
  if (year === ALL_YEARS) {
    const all = new Set<number>();
    for (const months of monthsByYear.values()) {
      for (const m of months) all.add(m);
    }
    return [...all].sort((a, b) => a - b);
  }
  return monthsByYear.get(year) ?? [];
}

export function tradeSourceLabel(
  source: string,
  transCode: string | null | undefined,
  labels: { csv: string; journal: string; manual: string; robinhood: string },
): string {
  const tc = (transCode ?? "").toUpperCase();
  if (tc.startsWith("MCP-")) return labels.robinhood;
  if (source === "csv") return labels.csv;
  if (source === "journal") return labels.journal;
  return labels.manual;
}

export function formatTradeAmount(amount: number | null | undefined): string {
  if (amount == null || Number.isNaN(amount)) return "—";
  const sign = amount < 0 ? "-" : "";
  return `${sign}$${Math.abs(amount).toFixed(2)}`;
}

/** Compact share display — trims noise from fractional MCP fills. */
export function formatTradeQuantity(qty: number | null | undefined): string {
  if (qty == null || Number.isNaN(qty)) return "—";
  if (Number.isInteger(qty) || Math.abs(qty - Math.round(qty)) < 1e-6) {
    return String(Math.round(qty));
  }
  const rounded = Math.round(qty * 10000) / 10000;
  return rounded.toFixed(4).replace(/\.?0+$/, "");
}

export function formatTradePrice(price: number | null | undefined): string {
  if (price == null || Number.isNaN(price)) return "—";
  const digits = Math.abs(price) >= 100 ? 2 : 4;
  const raw = price.toFixed(digits);
  return `$${raw.replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "")}`;
}

export function dedupeTradeRows(rows: LedgerEntry[]): LedgerEntry[] {
  const best = new Map<string, LedgerEntry>();
  for (const row of rows) {
    const key =
      row.row_hash ||
      `${row.activity_date ?? ""}|${row.symbol}|${row.side}|${row.quantity ?? ""}|${row.price ?? ""}`;
    const prev = best.get(key);
    if (!prev || (row.id ?? 0) > (prev.id ?? 0)) {
      best.set(key, row);
    }
  }
  return [...best.values()].sort(compareLedgerRowsDesc);
}
