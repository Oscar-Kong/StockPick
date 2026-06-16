"use client";

import clsx from "clsx";
import { fmt, useTranslation } from "@/lib/i18n";

interface ConfidenceBadgeProps {
  value: number;
  className?: string;
}

export function ConfidenceBadge({ value, className }: ConfidenceBadgeProps) {
  const { t } = useTranslation();
  const color =
    value >= 70
      ? "border-emerald-500/30 text-emerald-300"
      : value >= 45
        ? "border-amber-500/30 text-amber-200"
        : "border-zinc-600 text-zinc-400";

  return (
    <span className={clsx("chip px-1.5 py-0.5 text-xs font-medium tabular-nums", color, className)}>
      {fmt(t.quant.confidenceShort, { value: value.toFixed(0) })}
    </span>
  );
}
