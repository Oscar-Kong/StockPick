"use client";

import { PRICE_CHART_SERIES } from "@/lib/chartSeries";

type ChartTooltipProps = {
  active?: boolean;
  label?: string | number;
  payload?: {
    name?: string;
    dataKey?: string | number;
    value?: number | string | null;
    color?: string;
  }[];
};

const COLOR_BY_KEY = Object.fromEntries(
  PRICE_CHART_SERIES.map((s) => [s.key, s.color])
) as Record<string, string>;

export function PriceChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const ordered = [...payload].sort((a, b) => {
    const order = ["close", "ma10", "ma50", "ma200"];
    return order.indexOf(String(a.dataKey)) - order.indexOf(String(b.dataKey));
  });

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      {label != null && label !== "" && (
        <p className="mb-1.5 font-medium text-zinc-200">{String(label)}</p>
      )}
      <ul className="space-y-0.5">
        {ordered.map((entry) => {
          if (entry.value == null || entry.value === "") return null;
          const key = String(entry.dataKey ?? "");
          const color = COLOR_BY_KEY[key] ?? entry.color ?? "#7dff8e";
          return (
            <li key={key} className="flex items-center justify-between gap-4 tabular-nums">
              <span className="flex items-center gap-1.5 text-zinc-400">
                <span className="inline-block h-0.5 w-3 rounded-full" style={{ background: color }} />
                {entry.name ?? key}
              </span>
              <span className="font-medium" style={{ color }}>
                ${Number(entry.value).toFixed(2)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export const darkTooltipCursor = { fill: "rgba(0, 200, 5, 0.06)" };
