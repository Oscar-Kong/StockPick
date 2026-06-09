"use client";

import clsx from "clsx";

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "ok" | "warn" | "error";
  className?: string;
}

const TONE: Record<NonNullable<MetricCardProps["tone"]>, string> = {
  default: "text-zinc-100",
  ok: "text-[#7dff8e]",
  warn: "text-amber-300",
  error: "text-red-300",
};

export function MetricCard({ label, value, hint, tone = "default", className }: MetricCardProps) {
  return (
    <div className={clsx("surface-card p-3", className)}>
      <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{label}</p>
      <p className={clsx("mt-1 text-lg font-semibold tabular-nums", TONE[tone])}>{value}</p>
      {hint && <p className="mt-1 text-xs text-zinc-500">{hint}</p>}
    </div>
  );
}
