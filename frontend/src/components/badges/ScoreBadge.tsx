"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface ScoreBadgeProps {
  score: number;
  className?: string;
}

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  const { t } = useTranslation();
  const color =
    score >= 70
      ? "border-emerald-500/30 text-emerald-300"
      : score >= 45
        ? "border-amber-500/30 text-amber-200"
        : "border-zinc-600 text-zinc-400";

  return (
    <span
      className={clsx("chip px-1.5 py-0.5 text-[10px] font-semibold tabular-nums", color, className)}
      title={t.common.score}
    >
      {score.toFixed(0)}
    </span>
  );
}
