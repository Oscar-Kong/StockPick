import type {
  Bucket,
  PortfolioSourceType,
  PortfolioSummaryResponse,
  RebalanceHoldingInput,
} from "./types";

export const WEIGHT_SUM_TOLERANCE = 1e-6;

export function parseSymbols(raw: string): string[] {
  return [...new Set(raw.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean))];
}

export function buildExposureCacheKey(input: {
  symbols: string[];
  lookback: string;
  benchmark: string;
}): string {
  return JSON.stringify({
    symbols: [...input.symbols].sort(),
    lookback: input.lookback,
    benchmark: input.benchmark,
  });
}

export function checkOptimizationFeasibility(
  assetCount: number,
  maxWeight: number,
  cashBuffer: number
): { feasible: boolean; reason?: string; capacityPct: number; targetPct: number } {
  const targetPct = (1 - cashBuffer) * 100;
  const capacityPct = assetCount * maxWeight * 100;
  if (assetCount < 2) {
    return { feasible: false, reason: "Need at least 2 symbols.", capacityPct, targetPct };
  }
  if (capacityPct + WEIGHT_SUM_TOLERANCE * 100 < targetPct) {
    return {
      feasible: false,
      capacityPct,
      targetPct,
      reason: `${assetCount} assets × ${(maxWeight * 100).toFixed(0)}% maximum weight = ${capacityPct.toFixed(0)}% total capacity. Invested target is ${targetPct.toFixed(0)}%. Increase max weight, add assets, or raise cash reserve.`,
    };
  }
  return { feasible: true, capacityPct, targetPct };
}

export type PortfolioSleeve = Bucket | "custom";

export function sleeveLabel(sleeve: PortfolioSleeve): string {
  if (sleeve === "custom") return "Custom basket";
  return sleeve.charAt(0).toUpperCase() + sleeve.slice(1);
}

export function sourceLabel(source: PortfolioSourceType): string {
  switch (source) {
    case "current":
      return "Current Portfolio";
    case "watchlist":
      return "Watchlist Scenario";
    case "custom":
      return "Custom Basket";
  }
}

export function formatFreshnessDate(iso: string | null | undefined): string {
  if (!iso) return "Unavailable";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatDateRange(start?: string | null, end?: string | null): string {
  if (!start || !end) return "—";
  const fmt = (s: string) => {
    const d = new Date(s);
    return Number.isNaN(d.getTime())
      ? s
      : d.toLocaleDateString(undefined, { month: "long", day: "numeric", year: "numeric" });
  };
  return `${fmt(start)} – ${fmt(end)}`;
}

export function equalWeightSymbols(symbols: string[]): Record<string, number> {
  if (!symbols.length) return {};
  const w = 1 / symbols.length;
  return Object.fromEntries(symbols.map((s) => [s, w]));
}

/** Build rebalance holdings for active symbols; missing symbols start at 0 shares. */
export function buildRebalanceHoldings(
  activeSymbols: string[],
  summary: PortfolioSummaryResponse
): RebalanceHoldingInput[] {
  const bySym = new Map(summary.positions.map((p) => [p.symbol, p]));
  return activeSymbols.map((symbol) => {
    const p = bySym.get(symbol);
    return {
      symbol,
      shares: p?.shares ?? 0,
      avg_cost: p?.avg_cost ?? undefined,
      price: p?.price ?? undefined,
    };
  });
}

export interface DrawdownPoint {
  date: string;
  drawdown_pct: number;
}

/** Peak-to-trough drawdown series from normalized equity curve (0–100 scale). */
export function computeDrawdownSeries(
  equityCurve: { date: string; equity: number }[]
): DrawdownPoint[] {
  if (!equityCurve.length) return [];
  let peak = equityCurve[0].equity;
  return equityCurve.map((p) => {
    peak = Math.max(peak, p.equity);
    const dd = peak > 0 ? ((p.equity - peak) / peak) * 100 : 0;
    return { date: p.date, drawdown_pct: dd };
  });
}

export function bucketExposure(
  positions: PortfolioSummaryResponse["positions"]
): { bucket: string; weight: number; value: number }[] {
  const totals = new Map<string, { weight: number; value: number }>();
  for (const p of positions) {
    const key = p.bucket?.trim() || "Unclassified";
    const cur = totals.get(key) ?? { weight: 0, value: 0 };
    cur.weight += p.weight ?? 0;
    cur.value += p.market_value ?? 0;
    totals.set(key, cur);
  }
  return [...totals.entries()]
    .map(([bucket, v]) => ({ bucket, ...v }))
    .sort((a, b) => b.weight - a.weight);
}
