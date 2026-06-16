"use client";

import type { QuantLabTrustIndicator } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

const TRUST_STYLES: Record<QuantLabTrustIndicator, string> = {
  fresh: "border-emerald-900/50 bg-emerald-950/40 text-emerald-200",
  stale: "border-amber-900/50 bg-amber-950/40 text-amber-200",
  insufficient_sample: "border-zinc-700 bg-zinc-900/60 text-zinc-400",
  feature_disabled: "border-zinc-700 bg-zinc-950/60 text-zinc-500",
  no_saved_run: "border-zinc-800 bg-zinc-950/40 text-zinc-500",
  research_only: "border-sky-900/40 bg-sky-950/30 text-sky-200/90",
  needs_attention: "border-rose-900/50 bg-rose-950/40 text-rose-200",
};

export function QuantLabTrustBadge({ indicator }: { indicator: QuantLabTrustIndicator }) {
  const { t } = useTranslation();
  const labels: Record<QuantLabTrustIndicator, string> = {
    fresh: t.quantLab.trustFresh,
    stale: t.quantLab.trustStale,
    insufficient_sample: t.quantLab.trustInsufficientSample,
    feature_disabled: t.quantLab.trustFeatureDisabled,
    no_saved_run: t.quantLab.trustNoSavedRun,
    research_only: t.quantLab.trustResearchOnly,
    needs_attention: t.quantLab.trustNeedsAttention,
  };
  return (
    <span
      className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${TRUST_STYLES[indicator]}`}
    >
      {labels[indicator]}
    </span>
  );
}
