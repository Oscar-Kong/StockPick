"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { formatDateTime } from "@/lib/datetime";
import { useTranslation } from "@/lib/i18n";
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
    <section className="shrink-0 rounded-lg border border-zinc-800 bg-zinc-950/40 px-4 py-3">
      <h2 className="text-sm font-semibold text-zinc-200">{t.product.scanScoredTitle}</h2>
      <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-zinc-500">
            <TooltipLabel label={t.product.scoreSourceLabel} tooltip={t.product.scoreSourceTooltip} />
          </dt>
          <dd className="mt-1">
            {source ? (
              <ScoreSourceBadge source={source} />
            ) : (
              <span className="text-zinc-500">{t.product.scoreSourceUnknown}</span>
            )}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">
            <TooltipLabel label={t.product.parityLabel} tooltip={t.product.parityDeltaTooltip} />
          </dt>
          <dd className="mt-1 text-zinc-300">
            {hasParity ? t.product.parityAvailable : t.product.parityUnavailable}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">{t.scan.lastScan}</dt>
          <dd className="mt-1 tabular-nums text-zinc-300">
            {lastScanAt ? formatDateTime(lastScanAt) : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-zinc-500">
            <TooltipLabel label={t.product.dataFreshnessLabel} tooltip={t.product.staleEvidenceTooltip} />
          </dt>
          <dd className="mt-1">
            {lastScanAt ? (
              scanStale ? (
                <StaleDataBadge asOf={lastScanAt} />
              ) : (
                <span className="text-emerald-300/90">{t.product.dataFresh}</span>
              )
            ) : (
              <span className="text-zinc-500">—</span>
            )}
          </dd>
        </div>
      </dl>
      <p className="mt-3 text-xs">
        <Link href="/quant-lab" className="text-[#7dff8e] hover:underline">
          {t.product.openQuantLabValidation}
        </Link>
      </p>
    </section>
  );
}
