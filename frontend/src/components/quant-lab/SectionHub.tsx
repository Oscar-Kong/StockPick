"use client";

import {
  buildQuantLabHref,
  EXPERIMENT_LEGACY_LINKS,
  MONITOR_LEGACY_LINKS,
  RESULTS_LEGACY_LINKS,
  type QuantLabLegacyTab,
} from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";
import { useRouter } from "next/navigation";

const TAB_I18N: Record<QuantLabLegacyTab, keyof typeof import("@/lib/i18n/messages/en").en.quantLab> = {
  "factor-performance": "tabFactorPerformance",
  "walk-forward": "tabWalkForward",
  predictions: "tabPredictions",
  pairs: "tabPairs",
  "data-quality": "tabDataQuality",
  "model-admin": "tabModelAdmin",
};

interface SectionHubProps {
  kind: "experiments" | "results" | "model-monitor";
}

export function SectionHub({ kind }: SectionHubProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const links =
    kind === "experiments"
      ? EXPERIMENT_LEGACY_LINKS
      : kind === "results"
        ? RESULTS_LEGACY_LINKS
        : MONITOR_LEGACY_LINKS;

  const title =
    kind === "experiments"
      ? t.quantLab.navExperiments
      : kind === "results"
        ? t.quantLab.navResults
        : t.quantLab.navModelMonitor;

  const hint =
    kind === "experiments"
      ? t.quantLab.hubExperimentsHint
      : kind === "results"
        ? t.quantLab.hubResultsHint
        : t.quantLab.hubMonitorHint;

  return (
    <div className="space-y-3 text-sm">
      <p className="text-zinc-400">{hint}</p>
      <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
      <ul className="grid gap-2 sm:grid-cols-2">
        {links.map((tab) => (
          <li key={tab}>
            <button
              type="button"
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-left text-sm text-zinc-200 hover:border-zinc-600"
              onClick={() => router.push(buildQuantLabHref("legacy", { legacyTab: tab }))}
            >
              {t.quantLab[TAB_I18N[tab]]}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
