// Renders analysis alert pills and severity labels for a selected symbol.
"use client";

import { useTranslation } from "@/lib/i18n";
import type { AnalyzeAlert } from "@/lib/types";

const SEVERITY_STYLES: Record<string, string> = {
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function AnalysisAlerts({ alerts }: { alerts: AnalyzeAlert[] }) {
  const { t } = useTranslation();

  if (!alerts.length) {
    return <p className="text-xs text-zinc-500">{t.badges.noAlerts}</p>;
  }

  return (
    <ul className="space-y-2">
      {alerts.map((a, i) => (
        <li
          key={`${a.type}-${i}`}
          className={`rounded-md px-2 py-1.5 text-xs ${SEVERITY_STYLES[a.severity] ?? SEVERITY_STYLES.low}`}
        >
          <span className="font-medium capitalize">{a.type.replace("_", " ")}</span>
          {" — "}
          {a.message}
        </li>
      ))}
    </ul>
  );
}
