"use client";

import { QuantLabTrustBadge } from "./QuantLabTrustBadge";
import {
  USER_TRIGGERED_LAST_RUN_IDS,
  formatEvidenceDate,
  type LastRunCardId,
} from "@/lib/quantLabLastRun";
import type { QuantLabLastRunSummary } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";

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
    <article className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-xs font-semibold text-zinc-200">{title}</h3>
        <QuantLabTrustBadge indicator={summary.trust_indicator} />
      </div>

      {summary.available ? (
        <dl className="mb-3 space-y-1 text-xs">
          <div className="flex justify-between gap-2 text-zinc-500">
            <dt>{t.quantLab.lastRunGenerated}</dt>
            <dd className="tabular-nums text-zinc-400">{formatEvidenceDate(summary.generated_at)}</dd>
          </div>
          {summary.sample_size != null && (
            <div className="flex justify-between gap-2 text-zinc-500">
              <dt>{t.quantLab.lastRunSampleSize}</dt>
              <dd className="tabular-nums text-zinc-400">{summary.sample_size}</dd>
            </div>
          )}
          {summary.main_metric && (
            <div className="flex justify-between gap-2 text-zinc-500">
              <dt>{summary.main_metric.label}</dt>
              <dd className="font-medium tabular-nums text-zinc-300">{summary.main_metric.value}</dd>
            </div>
          )}
          {summary.status && (
            <div className="flex justify-between gap-2 text-zinc-500">
              <dt>{t.quantLab.runStatus}</dt>
              <dd className="capitalize text-zinc-400">{summary.status}</dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="mb-3 text-xs text-zinc-500">{summary.reason ?? t.quantLab.trustNoSavedRun}</p>
      )}

      {(summary.stale || summary.warnings.length > 0) && (
        <ul className="mb-3 space-y-0.5 text-[11px] text-amber-300/90">
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
        <p className="mb-3 text-[10px] text-sky-200/70">{t.quantLab.trustResearchOnly}</p>
      )}

      <div className="mt-auto flex flex-wrap gap-2 pt-1">
        <button type="button" onClick={onViewDetails} className="btn-ghost px-2 py-1 text-xs">
          {t.quantLab.viewDetails}
        </button>
        {showRunNew && (
          <button type="button" onClick={onRunNew} className="btn-primary px-2 py-1 text-xs">
            {t.quantLab.runNewResearch}
          </button>
        )}
      </div>
    </article>
  );
}
