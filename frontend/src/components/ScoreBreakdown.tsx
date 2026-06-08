// Chart component that visualizes weighted signal score contributions.
"use client";

import { ChartMount } from "@/components/ChartMount";
import { darkTooltipCursor, ScoreBreakdownTooltip } from "@/components/DarkChartTooltip";
import type { Signal } from "@/lib/types";
import {
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface ScoreBreakdownProps {
  signals: Signal[];
  className?: string;
}

export function ScoreBreakdown({ signals, className }: ScoreBreakdownProps) {
  const data = signals.map((s) => ({
    name: s.name,
    contribution: s.contribution,
    value: s.value,
  }));

  return (
    <ChartMount className={className ?? "analysis-chart-box h-72 w-full p-2"}>
      <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={200}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 8 }}>
          <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="name"
            width={120}
            tick={{ fontSize: 11 }}
          />
          <Tooltip
            content={<ScoreBreakdownTooltip />}
            cursor={darkTooltipCursor}
            wrapperStyle={{ outline: "none" }}
          />
          <Bar dataKey="contribution" fill="#00c805" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartMount>
  );
}
