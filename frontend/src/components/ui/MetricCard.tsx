"use client";

import { MetricTile, type MetricTileTone } from "./MetricTile";

interface MetricCardProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "ok" | "warn" | "error";
  className?: string;
}

const TONE_MAP: Record<NonNullable<MetricCardProps["tone"]>, MetricTileTone> = {
  default: "default",
  ok: "positive",
  warn: "warning",
  error: "negative",
};

/** Card-style metric — wraps MetricTile (card variant). */
export function MetricCard({ label, value, hint, tone = "default", className }: MetricCardProps) {
  return (
    <MetricTile
      label={label}
      value={value}
      hint={hint}
      tone={TONE_MAP[tone]}
      variant="card"
      className={className}
    />
  );
}
