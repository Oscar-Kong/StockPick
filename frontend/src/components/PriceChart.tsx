"use client";

import type { OhlcPoint } from "@/lib/chartSeries";
import {
  PRICE_CHART_SERIES,
  buildPriceChartSeries,
  latestMaSnapshot,
} from "@/lib/chartSeries";
import clsx from "clsx";
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
import { PriceChartTooltip, darkTooltipCursor } from "./PriceChartTooltip";

interface PriceChartProps {
  ohlc: OhlcPoint[];
  className?: string;
  heightClassName?: string;
  displayBars?: number;
  showLegend?: boolean;
  showSnapshot?: boolean;
}

export function PriceChart({
  ohlc,
  className,
  heightClassName = "h-[min(28rem,55vh)]",
  displayBars = 252,
  showLegend = true,
  showSnapshot = true,
}: PriceChartProps) {
  const data = buildPriceChartSeries(ohlc, displayBars);
  const snapshot = latestMaSnapshot(data);

  if (!data.length) {
    return <p className="p-4 text-sm text-zinc-500">No chart data available.</p>;
  }

  return (
    <div className={clsx("space-y-2", className)}>
      {showSnapshot && snapshot && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 text-sm tabular-nums text-zinc-500">
          <span>
            Close{" "}
            <span className="font-medium text-[#7dff8e]">${snapshot.close.toFixed(2)}</span>
          </span>
          {snapshot.ma10 != null && (
            <span>
              MA10 <span className="font-medium text-sky-300">${snapshot.ma10.toFixed(2)}</span>
            </span>
          )}
          {snapshot.ma50 != null && (
            <span>
              MA50 <span className="font-medium text-amber-300">${snapshot.ma50.toFixed(2)}</span>
            </span>
          )}
          {snapshot.ma200 != null && (
            <span>
              MA200 <span className="font-medium text-violet-300">${snapshot.ma200.toFixed(2)}</span>
            </span>
          )}
        </div>
      )}

      <ChartMount className={clsx("w-full min-w-0", heightClassName)}>
        <ResponsiveContainer width="100%" height="100%" minWidth={320} minHeight={240}>
          <LineChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" opacity={0.55} />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 10, fill: "#71717a" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={{ stroke: "#3f3f46" }}
              minTickGap={28}
            />
            <YAxis
              domain={["auto", "auto"]}
              tick={{ fontSize: 10, fill: "#71717a" }}
              axisLine={{ stroke: "#3f3f46" }}
              tickLine={{ stroke: "#3f3f46" }}
              width={56}
              tickFormatter={(v) => (typeof v === "number" ? v.toFixed(0) : String(v))}
            />
            <Tooltip
              content={<PriceChartTooltip />}
              cursor={darkTooltipCursor}
              wrapperStyle={{ outline: "none" }}
            />
            {showLegend && (
              <Legend
                verticalAlign="top"
                height={28}
                iconType="plainline"
                formatter={(value) => (
                  <span className="text-sm text-zinc-400">{value}</span>
                )}
              />
            )}
            {PRICE_CHART_SERIES.map((series) => (
              <Line
                key={series.key}
                type="monotone"
                dataKey={series.key}
                name={series.label}
                stroke={series.color}
                strokeWidth={series.width}
                dot={false}
                connectNulls={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </ChartMount>
    </div>
  );
}
