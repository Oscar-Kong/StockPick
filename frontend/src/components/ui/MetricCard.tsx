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
  ok: "text-brand",
  warn: "text-amber-300",
  error: "text-negative",
};

export function MetricCard({ label, value, hint, tone = "default", className }: MetricCardProps) {
  return (
    <div className={clsx("app-card p-4", className)}>
      <p className="text-label-caps">{label}</p>
      <p className={clsx("finance-value mt-2 text-lg font-semibold", TONE[tone])}>{value}</p>
      {hint && <p className="mt-1 text-xs text-tertiary">{hint}</p>}
    </div>
  );
}
