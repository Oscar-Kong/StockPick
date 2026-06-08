/** OHLC → chart rows with simple moving averages. */
export type OhlcPoint = { date: string; close: number };

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

/** Build chart rows; optionally trim to the last N sessions for display. */
export function buildPriceChartSeries(
  ohlc: OhlcPoint[],
  displayBars = 252
): PriceChartRow[] {
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

  if (displayBars > 0 && rows.length > displayBars) {
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
  };
}

export const PRICE_CHART_SERIES = [
  { key: "close" as const, label: "Close", color: "#00c805", width: 2 },
  { key: "ma10" as const, label: "MA10", color: "#38bdf8", width: 1.5 },
  { key: "ma50" as const, label: "MA50", color: "#fbbf24", width: 1.5 },
  { key: "ma200" as const, label: "MA200", color: "#a78bfa", width: 1.5 },
];
