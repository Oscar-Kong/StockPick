"use client";

import clsx from "clsx";
import { inferAlertSeverity } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";

const SEVERITY_STYLES = {
  critical: "border-red-500/25 bg-red-500/8 text-red-100",
  warning: "border-amber-500/25 bg-amber-500/8 text-amber-100",
  info: "border-white/8 bg-zinc-900/40 text-secondary",
} as const;

export function RiskAlertsPanel({ alerts }: { alerts: string[] }) {
  const { t } = useTranslation();
  if (!alerts.length) return null;

  const grouped = {
    critical: [] as string[],
    warning: [] as string[],
    info: [] as string[],
  };
  for (const alert of alerts) {
    grouped[inferAlertSeverity(alert)].push(alert);
  }

  const sections: { key: keyof typeof grouped; label: string }[] = [
    { key: "critical", label: t.home.dailyAlertCritical },
    { key: "warning", label: t.home.dailyAlertWarning },
    { key: "info", label: t.home.dailyAlertInfo },
  ];

  return (
    <SectionCard title={t.home.dailyRiskAlertsTitle} variant="muted">
      <div className="space-y-4">
        {sections.map(({ key, label }) =>
          grouped[key].length ? (
            <div key={key}>
              <p className="text-label-caps mb-2">{label}</p>
              <ul className="space-y-2">
                {grouped[key].map((alert) => (
                  <li
                    key={alert}
                    className={clsx("rounded-lg border px-3 py-2.5 text-sm leading-relaxed", SEVERITY_STYLES[key])}
                  >
                    {alert}
                  </li>
                ))}
              </ul>
            </div>
          ) : null
        )}
      </div>
    </SectionCard>
  );
}
