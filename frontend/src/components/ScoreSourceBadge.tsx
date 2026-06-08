"use client";

import { useTranslation } from "@/lib/i18n";
import type { ScoreSource } from "@/lib/v2Score";
import clsx from "clsx";

interface ScoreSourceBadgeProps {
  source: ScoreSource;
  className?: string;
}

export function ScoreSourceBadge({ source, className }: ScoreSourceBadgeProps) {
  const { t } = useTranslation();
  const isV2 = source === "scoring_engine_v2";
  const label = isV2 ? t.analysis.scoreSourceV2 : t.analysis.scoreSourceLegacy;

  return (
    <span
      className={clsx(
        "chip px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        isV2 ? "border-emerald-500/30 text-emerald-300" : "border-zinc-600 text-zinc-400",
        className
      )}
      title={t.analysis.scoreSourceHint}
    >
      {label}
    </span>
  );
}
