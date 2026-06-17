/** OHLC → chart rows with simple moving averages. */
export type OhlcPoint = { date: string; close: number };

export type ChartTimeRange = "1M" | "3M" | "6M" | "1Y";

export const CHART_RANGE_BARS: Record<ChartTimeRange, number> = {
  "1M": 21,
  "3M": 63,
  "6M": 126,
  "1Y": 252,
};

export type PriceChartRow = {
  date: string;
  fullDate: string;
  close: number;
  ma10: number | null;
  ma50: number | null;
  ma200: number | null;
};

function sma(values: number[], endIndex: number, period: number): number | null {
  if (endIndex + 1 < period) return null;
  const slice = values.slice(endIndex + 1 - period, endIndex + 1);
  return slice.reduce((sum, v) => sum + v, 0) / period;
}

/** Build chart rows from full history; MA uses all bars before optional display trim. */
export function buildPriceChartSeries(ohlc: OhlcPoint[], displayBars?: number): PriceChartRow[] {
  if (!ohlc.length) return [];

  const closes = ohlc.map((p) => p.close);
  const rows: PriceChartRow[] = ohlc.map((p, i) => ({
    date: p.date.length >= 10 ? p.date.slice(5) : p.date,
    fullDate: p.date,
    close: p.close,
    ma10: sma(closes, i, 10),
    ma50: sma(closes, i, 50),
    ma200: sma(closes, i, 200),
  }));

  if (displayBars != null && displayBars > 0 && rows.length > displayBars) {
    return rows.slice(-displayBars);
  }
  return rows;
}

export function latestMaSnapshot(rows: PriceChartRow[]) {
  const last = rows[rows.length - 1];
  if (!last) return null;
  return {
    close: last.close,
    ma10: last.ma10,
    ma50: last.ma50,
    ma200: last.ma200,
    fullDate: last.fullDate,
  };
}

export function periodChangePct(rows: PriceChartRow[]): number | null {
  if (rows.length < 2) return null;
  const first = rows[0].close;
  const last = rows[rows.length - 1].close;
  if (first <= 0) return null;
  return ((last / first) - 1) * 100;
}

export const PRICE_CHART_SERIES = [
  { key: "close" as const, label: "Close", color: "#00c805", width: 2 },
  { key: "ma10" as const, label: "MA10", color: "#38bdf8", width: 1.25 },
  { key: "ma50" as const, label: "MA50", color: "#fbbf24", width: 1.25 },
  { key: "ma200" as const, label: "MA200", color: "#a78bfa", width: 1.25 },
];
