"use client";

import { StrategyVersionBadge } from "@/components/DataQualityBadge";
import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatTile } from "@/components/ui/StatTile";
import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation } from "@/lib/i18n";
import type { Bucket, ScanParitySummary } from "@/lib/types";
import type { ScoreSource } from "@/lib/v2Score";

interface ScanStatusPanelProps {
  bucket: Bucket;
  lastScanAt?: string | null;
  strategyVersion?: string | null;
  scoringEngineUsed?: boolean | null;
  paritySummary?: ScanParitySummary | null;
  scanStale?: boolean;
  resultCount?: number;
  onLoadLatest: () => void;
  onSaveSnapshot: () => void;
  savingScan?: boolean;
  canSave?: boolean;
}

export function ScanStatusPanel({
  bucket,
  lastScanAt,
  strategyVersion,
  scoringEngineUsed,
  paritySummary,
  scanStale,
  resultCount = 0,
  onLoadLatest,
  onSaveSnapshot,
  savingScan = false,
  canSave = false,
}: ScanStatusPanelProps) {
  const { t } = useTranslation();

  const source: ScoreSource | null =
    scoringEngineUsed == null ? null : scoringEngineUsed ? "scoring_engine_v2" : "legacy_screener";

  const hasParity =
    paritySummary != null &&
    (paritySummary.average_delta != null || paritySummary.max_delta != null);

  return (
    <section className="surface-card p-4 sm:p-5">
      <SectionHeader
        title={t.scan.statusTitle}
        subtitle={t.scan.statusSubtitle}
        action={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onLoadLatest}
              className="btn-ghost px-3 py-1.5 text-xs hover:bg-zinc-900/70"
            >
              {t.scan.loadLastScan}
            </button>
            <button
              type="button"
              onClick={onSaveSnapshot}
              disabled={savingScan || !canSave}
              className="btn-ghost px-3 py-1.5 text-xs hover:bg-zinc-900/70 disabled:opacity-50"
            >
              {savingScan ? t.common.saving : t.scan.saveSnapshot}
            </button>
          </div>
        }
      />

      <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label={t.scan.lastScanLabel}
          value={lastScanAt ? formatDateTime(lastScanAt) : "—"}
          hint={lastScanAt ? undefined : t.scan.noLatestScan}
        />
        <StatTile
          label={t.scan.resultCountLabel}
          value={
            <span className="tabular-nums text-buy">
              {resultCount > 0 ? resultCount : "—"}
            </span>
          }
          hint={resultCount > 0 ? t.scan.candidatesRanked : undefined}
        />
        <StatTile
          label={t.product.scoreSourceLabel}
          tooltip={t.product.scoreSourceTooltip}
          value={
            source ? (
              <ScoreSourceBadge source={source} />
            ) : (
              <span className="text-zinc-500">{t.product.scoreSourceUnknown}</span>
            )
          }
        />
        <StatTile
          label={t.scan.strategyVersionLabel}
          value={
            strategyVersion ? (
              <StrategyVersionBadge version={strategyVersion} />
            ) : (
              <span className="text-zinc-500">—</span>
            )
          }
        />
        <StatTile
          label={t.product.dataFreshnessLabel}
          tooltip={t.product.staleEvidenceTooltip}
          value={
            lastScanAt ? (
              scanStale ? (
                <StaleDataBadge asOf={lastScanAt} />
              ) : (
                <span className="text-emerald-300/90">{t.product.dataFresh}</span>
              )
            ) : (
              <span className="text-zinc-500">—</span>
            )
          }
        />
        <StatTile
          label={t.product.parityLabel}
          tooltip={t.product.parityDeltaTooltip}
          value={
            hasParity ? (
              <span className="tabular-nums text-zinc-200">
                {fmt(t.scan.parityDetail, {
                  avg: paritySummary?.average_delta?.toFixed(1) ?? "—",
                  max: paritySummary?.max_delta?.toFixed(1) ?? "—",
                  diffs: String(paritySummary?.recommendation_bucket_diffs ?? 0),
                })}
              </span>
            ) : (
              <span className="text-zinc-500">{t.product.parityUnavailable}</span>
            )
          }
          hint={hasParity ? t.scan.parityHint : undefined}
        />
      </dl>

      {bucket === "penny" && (
        <p className="mt-4 rounded-lg border border-amber-900/30 bg-amber-950/20 px-3 py-2 text-xs leading-relaxed text-amber-200/90">
          {t.scan.rescanHint}
        </p>
      )}
    </section>
  );
}
