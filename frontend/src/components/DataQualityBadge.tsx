// Displays data quality score and the top data integrity warning.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";

interface DataQualityBadgeProps {
  score?: number | null;
  flags?: string[];
}

export function DataQualityBadge({ score, flags }: DataQualityBadgeProps) {
  const { t } = useTranslation();
  if (score == null) return null;

  const color =
    score >= 70
      ? "bg-buy/20 text-buy"
      : score >= 40
        ? "bg-amber-950/70 text-amber-300"
        : "bg-red-950/70 text-red-300";

  return (
    <div className="surface-card space-y-1 p-3">
      <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${color}`}>
        {fmt(t.badges.dataQuality, { score: score.toFixed(0) })}
      </span>
      {flags && flags.length > 0 && (
        <p className="text-xs text-zinc-500">{flags[0]}</p>
      )}
    </div>
  );
}

interface StrategyVersionBadgeProps {
  version?: string | null;
}

export function StrategyVersionBadge({ version }: StrategyVersionBadgeProps) {
  const { t } = useTranslation();
  if (!version) return null;
  return (
    <span className="inline-block rounded-full bg-zinc-900 px-2 py-0.5 text-xs text-zinc-300">
      {fmt(t.badges.strategy, { version })}
    </span>
  );
}
