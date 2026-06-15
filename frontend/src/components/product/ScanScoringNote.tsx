"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { StatTile } from "@/components/ui/StatTile";
import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation } from "@/lib/i18n";
import type { ScanParitySummary } from "@/lib/types";
import type { ScoreSource } from "@/lib/v2Score";
import Link from "next/link";

interface ScanScoringNoteProps {
  scoringEngineUsed?: boolean | null;
  paritySummary?: ScanParitySummary | null;
  lastScanAt?: string | null;
  scanStale?: boolean;
}

export function ScanScoringNote({
  scoringEngineUsed,
  paritySummary,
  lastScanAt,
  scanStale,
}: ScanScoringNoteProps) {
  const { t } = useTranslation();

  const hasParity =
    paritySummary != null &&
    (paritySummary.average_delta != null || paritySummary.max_delta != null);

  const source: ScoreSource | null =
    scoringEngineUsed == null ? null : scoringEngineUsed ? "scoring_engine_v2" : "legacy_screener";

  return (
    <section className="surface-card p-4 sm:p-5">
      <h2 className="text-sm font-semibold text-zinc-200">{t.product.scanScoredTitle}</h2>
      <p className="mt-1 text-xs leading-relaxed text-zinc-500">{t.scan.scoringNoteSubtitle}</p>

      <dl className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
        />
        <StatTile
          label={t.scan.lastScanLabel}
          value={lastScanAt ? formatDateTime(lastScanAt) : "—"}
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
      </dl>

      <p className="mt-4 text-xs">
        <Link href="/quant-lab" className="text-[#7dff8e] hover:underline">
          {t.product.openQuantLabValidation}
        </Link>
      </p>
    </section>
  );
}
