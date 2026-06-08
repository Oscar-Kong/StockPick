// Badge group for valuation warnings and upcoming earnings markers.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";

interface ValuationBadgesProps {
  warnings?: string[];
  earningsSoon?: boolean;
  earningsDate?: string | null;
  daysUntil?: number | null;
}

export function ValuationBadges({
  warnings = [],
  earningsSoon,
  earningsDate,
  daysUntil,
}: ValuationBadgesProps) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-wrap gap-1">
      {earningsSoon && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          {daysUntil != null
            ? fmt(t.badges.earningsIn, { days: daysUntil })
            : t.badges.earningsSoon}
        </span>
      )}
      {!earningsSoon && earningsDate && (
        <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
          {fmt(t.badges.earningsOn, { date: earningsDate })}
        </span>
      )}
      {warnings.map((w) => (
        <span
          key={w}
          className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-950 dark:text-orange-300"
          title={w}
        >
          {w.length > 42 ? `${w.slice(0, 40)}…` : w}
        </span>
      ))}
    </div>
  );
}
