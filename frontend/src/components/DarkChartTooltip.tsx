// Dark-themed Recharts tooltip (default tooltip is a bright white box).
"use client";

type ChartTooltipProps = {
  active?: boolean;
  label?: string | number;
  payload?: { name?: string; dataKey?: string | number; value?: number | string; payload?: Record<string, unknown> }[];
};

export function DarkChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      {label != null && label !== "" && (
        <p className="mb-1 font-medium text-zinc-200">{String(label)}</p>
      )}
      <ul className="space-y-0.5">
        {payload.map((entry) => (
          <li key={entry.name ?? entry.dataKey} className="text-[#7dff8e]">
            <span className="text-zinc-400">{entry.name ?? entry.dataKey}: </span>
            {typeof entry.value === "number" ? entry.value.toFixed(2) : entry.value}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ScoreBreakdownTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const row = payload[0]?.payload as
    | { name?: string; contribution?: number; value?: number }
    | undefined;
  const name = (label as string) ?? row?.name ?? "";
  const contribution = row?.contribution ?? payload[0]?.value ?? 0;
  const signal = row?.value ?? 0;

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950/95 px-3 py-2 text-xs shadow-xl backdrop-blur-sm">
      {name && <p className="mb-1 font-medium text-zinc-200">{name}</p>}
      <p className="text-zinc-300">
        <span className="text-zinc-500">Contribution </span>
        <span className="font-medium text-[#7dff8e]">
          {Number(contribution).toFixed(1)}
        </span>
        <span className="text-zinc-500"> · signal </span>
        <span className="text-zinc-200">{Number(signal).toFixed(1)}</span>
      </p>
    </div>
  );
}

export const darkTooltipCursor = { fill: "rgba(0, 200, 5, 0.06)" };
