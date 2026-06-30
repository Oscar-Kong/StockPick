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
  default: "text-zinc-50",
  ok: "text-positive",
  warn: "text-amber-300",
  error: "text-negative",
};

export function MetricCard({ label, value, hint, tone = "default", className }: MetricCardProps) {
  return (
    <div className={clsx("metric-tile", className)}>
      <p className="metric-tile__label">{label}</p>
      <p className={clsx("metric-tile__value finance-value", TONE[tone])}>{value}</p>
      {hint && <p className="metric-tile__hint">{hint}</p>}
    </div>
  );
}
