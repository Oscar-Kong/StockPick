"use client";

import type { ChartTimeRange, OhlcPoint } from "@/lib/chartSeries";
import {
  CHART_RANGE_BARS,
  PRICE_CHART_SERIES,
  buildPriceChartSeries,
  latestMaSnapshot,
  periodChangePct,
} from "@/lib/chartSeries";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartMount } from "./ChartMount";
import { ChartTextSummary } from "./ui/ChartTextSummary";
import { PriceChartTooltip, darkTooltipCursor } from "./PriceChartTooltip";
import { StaleDataBadge } from "./badges/StaleDataBadge";

interface PriceChartProps {
  ohlc: OhlcPoint[];
  className?: string;
  heightClassName?: string;
  defaultRange?: ChartTimeRange;
  priceHistoryLastDate?: string | null;
  priceHistoryIsStale?: boolean;
  priceHistoryRefreshedAt?: string | null;
  showMaToggle?: boolean;
}

export function PriceChart({
  ohlc,
  className,
  heightClassName = "h-[min(24rem,50vh)]",
  defaultRange = "1Y",
  priceHistoryLastDate,
  priceHistoryIsStale,
  priceHistoryRefreshedAt,
  showMaToggle = true,
}: PriceChartProps) {
  const { t } = useTranslation();
  const [range, setRange] = useState<ChartTimeRange>(defaultRange);
  const [showMa, setShowMa] = useState(true);

  const displayBars = CHART_RANGE_BARS[range];
  const fullSeries = useMemo(() => buildPriceChartSeries(ohlc), [ohlc]);
  const data = useMemo(
    () => buildPriceChartSeries(ohlc, displayBars),
    [ohlc, displayBars]
  );
  const snapshot = latestMaSnapshot(data);
  const periodChange = periodChangePct(data);
  const lastBarDate =
    priceHistoryLastDate ?? snapshot?.fullDate ?? (ohlc.length ? ohlc[ohlc.length - 1]?.date : null);

  const summaryLines = (() => {
    if (!data.length) return [];
    const cs = t.chartSummary;
    const lines: { label: string; value: string }[] = [
      { label: cs.period, value: range },
      { label: cs.startingValue, value: `$${data[0].close.toFixed(2)}` },
      { label: cs.endingValue, value: `$${data[data.length - 1].close.toFixed(2)}` },
    ];
    if (periodChange != null) {
      const sign = periodChange >= 0 ? "+" : "";
      lines.push({ label: cs.change, value: `${sign}${periodChange.toFixed(1)}%` });
    }
    if (lastBarDate) {
      lines.push({ label: cs.latestData, value: lastBarDate });
    }
    return lines;
  })();

  const series = showMa ? PRICE_CHART_SERIES : PRICE_CHART_SERIES.filter((s) => s.key === "close");

  if (!fullSeries.length) {
    return <p className="p-4 text-sm text-secondary">{t.analysis.chartNoData}</p>;
  }

  const ranges: ChartTimeRange[] = ["1M", "3M", "6M", "1Y"];

  return (
    <div className={clsx("price-chart", className)}>
      <div className="price-chart__header">
        <div className="price-chart__metrics">
          {snapshot && (
            <span className="price-chart__metric">
              {t.common.price}{" "}
              <span className="finance-value font-semibold text-foreground">${snapshot.close.toFixed(2)}</span>
            </span>
          )}
          {periodChange != null && (
            <span
              className={clsx(
                "price-chart__metric finance-value",
                periodChange >= 0 ? "text-positive" : "text-negative"
              )}
            >
              {range} {periodChange >= 0 ? "+" : ""}
              {periodChange.toFixed(1)}%
            </span>
          )}
          {lastBarDate && (
            <span className="price-chart__metric text-secondary">
              {t.analysis.latestBarLabel}{" "}
              <span className="finance-value text-zinc-200">{lastBarDate}</span>
            </span>
          )}
          {priceHistoryIsStale && lastBarDate ? (
            <StaleDataBadge asOf={lastBarDate} />
          ) : lastBarDate ? (
            <span className="text-sm text-positive">{t.analysis.priceHistoryFresh}</span>
          ) : null}
          {priceHistoryRefreshedAt && (
            <span className="price-chart__metric text-secondary">
              {t.analysis.priceHistoryRefreshed} {priceHistoryRefreshedAt.slice(0, 16).replace("T", " ")}
            </span>
          )}
        </div>
        <div className="price-chart__controls">
          {showMaToggle && (
            <label className="price-chart__toggle">
              <input type="checkbox" checked={showMa} onChange={(e) => setShowMa(e.target.checked)} />
              {t.analysis.chartShowMa}
            </label>
          )}
          <div className="price-chart__ranges" role="group" aria-label={t.analysis.chartRangeAria}>
            {ranges.map((r) => (
              <button
                key={r}
                type="button"
                className={clsx("price-chart__range-btn", range === r && "price-chart__range-btn--active")}
                onClick={() => setRange(r)}
                aria-pressed={range === r}
              >
                {t.analysis.chartRange[r]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <ChartMount className={clsx("w-full min-w-0", heightClassName)}>
        <ResponsiveContainer width="100%" height="100%" minWidth={280} minHeight={220}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" opacity={0.45} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 12, fill: "#a1a1aa" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              minTickGap={48}
              interval="preserveStartEnd"
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 12, fill: "#a1a1aa" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={false}
              width={52}
              tickFormatter={(v) => (typeof v === "number" ? v.toFixed(0) : String(v))}
            />
            <Tooltip
              content={<PriceChartTooltip />}
              cursor={darkTooltipCursor}
              wrapperStyle={{ outline: "none" }}
            />
            <Legend
              verticalAlign="top"
              height={24}
              iconType="plainline"
              formatter={(value) => <span className="text-sm text-secondary">{value}</span>}
            />
            {series.map((s) => (
              <Line
                key={s.key}
                type="monotone"
                dataKey={s.key}
                name={s.label}
                stroke={s.color}
                strokeWidth={s.width}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartMount>
      <ChartTextSummary lines={summaryLines} srOnly />
    </div>
  );
}
