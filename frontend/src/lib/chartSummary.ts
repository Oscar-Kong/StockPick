/** Concise textual summaries for chart accessibility — no extra API calls. */

export type ChartSummaryLine = { label: string; value: string };

export function formatPct(value: number | null | undefined, digits = 1): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function formatUsd(value: number | null | undefined, digits = 2): string | null {
  if (value == null || !Number.isFinite(value)) return null;
  return `$${value.toFixed(digits)}`;
}

export function maxDrawdownFromSeries(values: Array<number | null | undefined>): number | null {
  let peak = -Infinity;
  let maxDd = 0;
  for (const raw of values) {
    if (raw == null || !Number.isFinite(raw)) continue;
    if (raw > peak) peak = raw;
    if (peak > 0) {
      const dd = ((raw - peak) / peak) * 100;
      if (dd < maxDd) maxDd = dd;
    }
  }
  return maxDd < 0 ? maxDd : null;
}

export function periodReturnPct(
  start: number | null | undefined,
  end: number | null | undefined
): number | null {
  if (start == null || end == null || !Number.isFinite(start) || !Number.isFinite(end) || start <= 0) {
    return null;
  }
  return ((end / start) - 1) * 100;
}

export type PriceChartSummaryInput = {
  periodLabel: string;
  startPrice: number | null;
  endPrice: number | null;
  periodChangePct: number | null;
  latestDate: string | null;
};

export function buildPriceChartSummaryLines(input: PriceChartSummaryInput): ChartSummaryLine[] {
  const lines: ChartSummaryLine[] = [];
  if (input.periodLabel) {
    lines.push({ label: "Period", value: input.periodLabel });
  }
  const start = formatUsd(input.startPrice);
  const end = formatUsd(input.endPrice);
  if (start) lines.push({ label: "Starting value", value: start });
  if (end) lines.push({ label: "Ending value", value: end });
  const change = formatPct(input.periodChangePct);
  if (change) lines.push({ label: "Change", value: change });
  if (input.latestDate) {
    lines.push({ label: "Latest data", value: input.latestDate });
  }
  return lines;
}

export type EquityChartSummaryInput = {
  periodLabel?: string | null;
  startEquity: number | null;
  endEquity: number | null;
  benchmarkStart?: number | null;
  benchmarkEnd?: number | null;
  maxDrawdownPct?: number | null;
  latestDate?: string | null;
};

export function buildEquityChartSummaryLines(input: EquityChartSummaryInput): ChartSummaryLine[] {
  const lines: ChartSummaryLine[] = [];
  if (input.periodLabel) {
    lines.push({ label: "Period", value: input.periodLabel });
  }
  const start = formatUsd(input.startEquity);
  const end = formatUsd(input.endEquity);
  if (start) lines.push({ label: "Starting value", value: start });
  if (end) lines.push({ label: "Ending value", value: end });
  const change = periodReturnPct(input.startEquity, input.endEquity);
  const changeFmt = formatPct(change);
  if (changeFmt) lines.push({ label: "Portfolio change", value: changeFmt });
  const benchChange = periodReturnPct(input.benchmarkStart, input.benchmarkEnd);
  const benchFmt = formatPct(benchChange);
  if (benchFmt) lines.push({ label: "Benchmark change", value: benchFmt });
  if (input.maxDrawdownPct != null && Number.isFinite(input.maxDrawdownPct)) {
    lines.push({ label: "Maximum drawdown", value: `${input.maxDrawdownPct.toFixed(1)}%` });
  }
  if (input.latestDate) {
    lines.push({ label: "Latest data", value: input.latestDate });
  }
  return lines;
}

export function buildSeriesChartSummaryLines(
  title: string,
  rows: Array<Record<string, string | number | null>>,
  seriesNames: string[]
): ChartSummaryLine[] {
  if (!rows.length || !seriesNames.length) return [{ label: "Chart", value: title }];
  const first = rows[0];
  const last = rows[rows.length - 1];
  const lines: ChartSummaryLine[] = [{ label: "Chart", value: title }];
  const xStart = first?.x != null ? String(first.x) : null;
  const xEnd = last?.x != null ? String(last.x) : null;
  if (xStart && xEnd) {
    lines.push({ label: "Range", value: xStart === xEnd ? xStart : `${xStart} – ${xEnd}` });
  }
  for (const name of seriesNames) {
    const s = typeof first?.[name] === "number" ? (first[name] as number) : null;
    const e = typeof last?.[name] === "number" ? (last[name] as number) : null;
    const ch = periodReturnPct(s, e);
    const chFmt = formatPct(ch);
    if (chFmt) lines.push({ label: name, value: chFmt });
  }
  return lines;
}
