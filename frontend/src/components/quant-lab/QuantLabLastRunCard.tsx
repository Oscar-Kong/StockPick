"use client";

import { QuantLabTrustBadge } from "./QuantLabTrustBadge";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { StatTile } from "@/components/ui/StatTile";
import {
  USER_TRIGGERED_LAST_RUN_IDS,
  formatEvidenceDate,
  type LastRunCardId,
} from "@/lib/quantLabLastRun";
import type { QuantLabLastRunSummary } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { SecondaryButton, PrimaryButton } from "@/components/ui/buttons";

interface QuantLabLastRunCardProps {
  summary: QuantLabLastRunSummary;
  title: string;
  onViewDetails: () => void;
  onRunNew?: () => void;
}

export function QuantLabLastRunCard({
  summary,
  title,
  onViewDetails,
  onRunNew,
}: QuantLabLastRunCardProps) {
  const { t } = useTranslation();
  const showRunNew =
    onRunNew && USER_TRIGGERED_LAST_RUN_IDS.has(summary.id as LastRunCardId);

  const warnings = [
    ...new Set(
      [
        summary.stale && summary.stale_reason ? summary.stale_reason : null,
        ...summary.warnings,
      ].filter(Boolean) as string[]
    ),
  ];

  return (
    <GlassPanel as="article" variant="default" className="flex h-full min-h-0 flex-col">
      <div className="mb-4 flex min-w-0 items-start justify-between gap-2">
        <h3 className="min-w-0 text-sm font-semibold leading-snug text-zinc-100">{title}</h3>
        <QuantLabTrustBadge indicator={summary.trust_indicator} />
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-3">
        {summary.available ? (
          <dl className="grid min-w-0 grid-cols-2 gap-3">
            <StatTile
              label={t.quantLab.lastRunGenerated}
              value={formatEvidenceDate(summary.generated_at)}
            />
            <StatTile
              label={t.quantLab.lastRunSampleSize}
              value={
                summary.sample_size != null ? (
                  <span className="tabular-nums">{summary.sample_size}</span>
                ) : (
                  "—"
                )
              }
            />
            <StatTile
              label={t.quantLab.runStatus}
              value={
                summary.status ? (
                  <span className="capitalize">{summary.status}</span>
                ) : (
                  "—"
                )
              }
            />
            <StatTile
              label={summary.main_metric?.label ?? t.quantLab.lastRunMetricFallback}
              value={
                summary.main_metric ? (
                  <span className="text-base font-semibold tabular-nums text-zinc-50">
                    {summary.main_metric.value}
                  </span>
                ) : (
                  "—"
                )
              }
              truncateTitle={summary.main_metric?.value}
            />
          </dl>
        ) : (
          <p className="text-sm leading-relaxed text-secondary">
            {summary.reason ?? t.quantLab.trustNoSavedRun}
          </p>
        )}

        {(warnings.length > 0 || summary.research_only) && (
          <div className="space-y-1.5">
            {warnings.length > 0 && (
              <ul className="space-y-1 text-xs leading-relaxed text-amber-300">
                {warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            )}
            {summary.research_only && (
              <p className="text-xs leading-relaxed text-info">{t.quantLab.trustResearchOnly}</p>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 flex shrink-0 flex-col gap-2 border-t border-zinc-800/60 pt-4 sm:flex-row sm:flex-wrap">
        <SecondaryButton size="sm" onClick={onViewDetails} className="w-full rounded-lg sm:w-auto">
          {t.quantLab.viewDetails}
        </SecondaryButton>
        {showRunNew && (
          <PrimaryButton size="sm" onClick={onRunNew} className="w-full rounded-lg sm:w-auto">
            {t.quantLab.runNewResearch}
          </PrimaryButton>
        )}
      </div>
    </GlassPanel>
  );
}
