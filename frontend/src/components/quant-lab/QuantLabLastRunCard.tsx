"use client";

import { QuantLabTrustBadge } from "./QuantLabTrustBadge";
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

  return (
    <article className="app-card app-card--elevated flex flex-col p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-100">{title}</h3>
        <QuantLabTrustBadge indicator={summary.trust_indicator} />
      </div>

      {summary.available ? (
        <dl className="mb-3 grid gap-2 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-2 sm:flex-col sm:justify-start">
            <dt className="text-tertiary">{t.quantLab.lastRunGenerated}</dt>
            <dd className="finance-value text-secondary">{formatEvidenceDate(summary.generated_at)}</dd>
          </div>
          {summary.sample_size != null && (
            <div className="flex justify-between gap-2 sm:flex-col sm:justify-start">
              <dt className="text-tertiary">{t.quantLab.lastRunSampleSize}</dt>
              <dd className="finance-value text-zinc-100">{summary.sample_size}</dd>
            </div>
          )}
          {summary.main_metric && (
            <div className="flex justify-between gap-2 sm:col-span-2 sm:flex-col sm:justify-start">
              <dt className="text-tertiary">{summary.main_metric.label}</dt>
              <dd className="finance-value text-base font-semibold text-zinc-50">{summary.main_metric.value}</dd>
            </div>
          )}
          {summary.status && (
            <div className="flex justify-between gap-2 sm:flex-col sm:justify-start">
              <dt className="text-tertiary">{t.quantLab.runStatus}</dt>
              <dd className="capitalize text-secondary">{summary.status}</dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="mb-3 text-sm text-secondary">{summary.reason ?? t.quantLab.trustNoSavedRun}</p>
      )}

      {(summary.stale || summary.warnings.length > 0) && (
        <ul className="mb-3 space-y-1 text-xs text-amber-300">
          {[
            ...new Set(
              [
                summary.stale && summary.stale_reason ? summary.stale_reason : null,
                ...summary.warnings,
              ].filter(Boolean) as string[]
            ),
          ].map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      {summary.research_only && (
        <p className="mb-3 text-xs text-info">{t.quantLab.trustResearchOnly}</p>
      )}

      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <SecondaryButton size="sm" onClick={onViewDetails} className="rounded-lg">
          {t.quantLab.viewDetails}
        </SecondaryButton>
        {showRunNew && (
          <PrimaryButton size="sm" onClick={onRunNew} className="rounded-lg">
            {t.quantLab.runNewResearch}
          </PrimaryButton>
        )}
      </div>
    </article>
  );
}
