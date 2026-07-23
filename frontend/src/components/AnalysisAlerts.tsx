// Compact inline alert chips for analysis warnings (severity + type).
"use client";

import { useTranslation } from "@/lib/i18n";
import type { AnalyzeAlert } from "@/lib/types";

const SEVERITY_STYLES: Record<string, string> = {
  high: "border-red-800/60 bg-red-950/40 text-red-300",
  medium: "border-amber-800/50 bg-amber-950/35 text-amber-200",
  low: "border-zinc-700/80 bg-zinc-900/60 text-zinc-300",
};

export function AnalysisAlerts({ alerts }: { alerts: AnalyzeAlert[] }) {
  const { t } = useTranslation();

  if (!alerts.length) {
    return <p className="text-xs text-zinc-500">{t.badges.noAlerts}</p>;
  }

  return (
    <ul className="analysis-alerts" role="list">
      {alerts.map((a, i) => (
        <li
          key={`${a.type}-${i}`}
          className={`analysis-alert-chip ${SEVERITY_STYLES[a.severity] ?? SEVERITY_STYLES.low}`}
        >
          <span className="analysis-alert-chip__type">{a.type.replace("_", " ")}</span>
          <span className="analysis-alert-chip__msg">{a.message}</span>
        </li>
      ))}
    </ul>
  );
}
