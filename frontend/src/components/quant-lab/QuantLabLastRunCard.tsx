"use client";

import { QuantLabTrustBadge } from "./QuantLabTrustBadge";
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

  return (
    <article className="app-card app-card--elevated flex flex-col p-4 sm:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-zinc-100">{title}</h3>
        <QuantLabTrustBadge indicator={summary.trust_indicator} />
      </div>

      {summary.available ? (
        <dl className="mb-4 grid gap-3 sm:grid-cols-2">
          <StatTile
            label={t.quantLab.lastRunGenerated}
            value={formatEvidenceDate(summary.generated_at)}
          />
          {summary.sample_size != null && (
            <StatTile
              label={t.quantLab.lastRunSampleSize}
              value={<span className="tabular-nums">{summary.sample_size}</span>}
            />
          )}
          {summary.status && (
            <StatTile
              label={t.quantLab.runStatus}
              value={<span className="capitalize">{summary.status}</span>}
            />
          )}
          {summary.main_metric && (
            <StatTile
              label={summary.main_metric.label}
              value={
                <span className="text-base font-semibold tabular-nums text-zinc-50">
                  {summary.main_metric.value}
                </span>
              }
              className={summary.status ? undefined : "sm:col-span-2"}
            />
          )}
        </dl>
      ) : (
        <p className="mb-4 text-sm leading-relaxed text-secondary">{summary.reason ?? t.quantLab.trustNoSavedRun}</p>
      )}

      {(summary.stale || summary.warnings.length > 0) && (
        <ul className="mb-4 space-y-1.5 text-xs leading-relaxed text-amber-300">
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
        <p className="mb-4 text-xs leading-relaxed text-info">{t.quantLab.trustResearchOnly}</p>
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
