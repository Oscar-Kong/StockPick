"use client";

import type { ChartSeries } from "@/lib/types";
import { buildSeriesChartSummaryLines } from "@/lib/chartSummary";
import { ChartTextSummary } from "@/components/ui/ChartTextSummary";
import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface ResultChartProps {
  chart: ChartSeries;
}

function flattenSeries(chart: ChartSeries) {
  const rows: Array<Record<string, string | number | null>> = [];
  for (const s of chart.series) {
    for (const point of s.data ?? []) {
      const x = point.x ?? point.label ?? "";
      const existing = rows.find((r) => r.x === x);
      const y = typeof point.y === "number" && Number.isFinite(point.y) ? point.y : null;
      if (existing) {
        existing[s.name] = y;
      } else {
        rows.push({ x: String(x), [s.name]: y });
      }
    }
  }
  return rows;
}

export function ResultChart({ chart }: ResultChartProps) {
  const seriesNames = useMemo(() => chart.series.map((s) => s.name), [chart.series]);
  const data = useMemo(() => flattenSeries(chart), [chart]);
  const summaryLines = useMemo(
    () => buildSeriesChartSummaryLines(chart.title, data, seriesNames),
    [chart.title, data, seriesNames]
  );

  if (chart.empty_reason) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-500">
        <p className="font-medium text-zinc-300">{chart.title}</p>
        <p className="mt-1">{chart.empty_reason}</p>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3 text-xs text-zinc-500">
        <p className="font-medium text-zinc-300">{chart.title}</p>
        <p className="mt-1">No chart data</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
      <p className="mb-2 text-xs font-medium text-zinc-300">{chart.title}</p>
      <ChartTextSummary lines={summaryLines} className="mb-2" />
      <div className="h-48 w-full">
        <ResponsiveContainer width="100%" height="100%">
          {chart.chart_type === "bar" ? (
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
              <XAxis dataKey="x" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} />
              {seriesNames.map((name, i) => (
                <Bar key={name} dataKey={name} fill={i === 0 ? "#38bdf8" : "#a78bfa"} isAnimationActive={false} />
              ))}
            </BarChart>
          ) : (
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
              <XAxis dataKey="x" tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <YAxis tick={{ fill: "#a1a1aa", fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#18181b", border: "1px solid #3f3f46" }} />
              {seriesNames.map((name, i) => (
                <Line
                  key={name}
                  type="monotone"
                  dataKey={name}
                  stroke={i === 0 ? "#38bdf8" : "#a78bfa"}
                  dot={false}
                  connectNulls={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
