"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { GlassPanel } from "@/components/ui/GlassPanel";
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
    <GlassPanel variant="hero" className="scan-scoring-note" aria-label={t.product.scanScoredTitle}>
      <div>
        <h2 className="text-sm font-semibold text-foreground">{t.product.scanScoredTitle}</h2>
        <p className="mt-1 text-xs leading-relaxed text-secondary">{t.scan.scoringNoteSubtitle}</p>
      </div>

      <dl className="analysis-hero__stats stat-tile-grid">
        <StatTile
          label={t.product.scoreSourceLabel}
          tooltip={t.product.scoreSourceTooltip}
          value={
            source ? (
              <ScoreSourceBadge source={source} />
            ) : (
              <span className="text-secondary">{t.product.scoreSourceUnknown}</span>
            )
          }
        />
        <StatTile
          label={t.product.parityLabel}
          tooltip={t.product.parityDeltaTooltip}
          value={
            hasParity ? (
              <span className="tabular-nums text-foreground">
                {fmt(t.scan.parityDetail, {
                  avg: paritySummary?.average_delta?.toFixed(1) ?? "—",
                  max: paritySummary?.max_delta?.toFixed(1) ?? "—",
                  diffs: String(paritySummary?.recommendation_bucket_diffs ?? 0),
                })}
              </span>
            ) : (
              <span className="text-secondary">{t.product.parityUnavailable}</span>
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
                <span className="text-positive">{t.product.dataFresh}</span>
              )
            ) : (
              <span className="text-secondary">—</span>
            )
          }
        />
      </dl>

      <p className="text-xs">
        <Link href="/quant-lab" className="text-primary hover:underline">
          {t.product.openQuantLabValidation}
        </Link>
      </p>
    </GlassPanel>
  );
}
