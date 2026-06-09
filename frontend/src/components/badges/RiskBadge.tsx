"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import type { RiskLevel } from "@/lib/types";

interface RiskBadgeProps {
  level: RiskLevel | string;
  className?: string;
}

const STYLE: Record<string, string> = {
  low: "border-emerald-500/30 text-emerald-300",
  medium: "border-amber-500/30 text-amber-200",
  high: "border-red-500/40 text-red-300",
};

export function RiskBadge({ level, className }: RiskBadgeProps) {
  const { t } = useTranslation();
  const key = level.toLowerCase() as keyof typeof t.risk;
  const label = t.risk[key] ?? level;
  const style = STYLE[level.toLowerCase()] ?? STYLE.medium;

  return (
    <span className={clsx("chip px-1.5 py-0.5 text-[10px] font-medium uppercase", style, className)}>
      {label}
    </span>
  );
}
