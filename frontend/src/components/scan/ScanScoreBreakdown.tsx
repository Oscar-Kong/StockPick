"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import {
  SCAN_SCORE_STRONG_MIN,
  SCAN_SCORE_WATCH_MIN,
  scoreBandForStock,
  scorePercentileInScan,
  type ScanScoreBand,
} from "@/lib/scanScoreBand";
import { readScanScoreParts } from "@/lib/scanScoreDisplay";
import type { StockResult } from "@/lib/types";

interface ScanScoreBreakdownProps {
  stock: StockResult;
  compact?: boolean;
  className?: string;
  /** All scores in the current scan — used for percentile tooltip. */
  scanScores?: number[];
}

function bandClass(band: ScanScoreBand): string {
  if (band === "strong") return "scan-score-band scan-score-band--strong";
  if (band === "watch") return "scan-score-band scan-score-band--watch";
  if (band === "fallback") return "scan-score-band scan-score-band--fallback";
  return "scan-score-band scan-score-band--skip";
}

/**
 * Scan table SCORE column — single ranking number + compact buy-band chip.
 * Buy / wait decision context lives in the Action column.
 */
export function ScanScoreBreakdown({
  stock,
  compact,
  className,
  scanScores,
}: ScanScoreBreakdownProps) {
  const { t } = useTranslation();
  const parts = readScanScoreParts(stock);
  const band = scoreBandForStock(stock);
  const percentile =
    scanScores && scanScores.length > 0
      ? scorePercentileInScan(parts.ranking, scanScores)
      : null;

  const bandLabel =
    band === "strong"
      ? t.scan.scoreBandStrong
      : band === "watch"
        ? t.scan.scoreBandWatch
        : band === "fallback"
          ? t.scan.scoreBandFallback
          : t.scan.scoreBandSkip;

  const titleParts = [
    t.scan.rankingScoreOnlyHint,
    band === "fallback"
      ? t.scan.scoreBandFallbackHint
      : t.scan.scoreBandHint
          .replace("{strong}", String(SCAN_SCORE_STRONG_MIN))
          .replace("{watch}", String(SCAN_SCORE_WATCH_MIN)),
  ];
  if (percentile != null) {
    titleParts.push(t.scan.scorePercentileHint.replace("{pct}", String(percentile)));
  }

  const sizeClass = compact ? "text-xs font-semibold" : "text-lg font-semibold";

  return (
    <span className={clsx("scan-score-cell", className)} title={titleParts.join(" ")}>
      <span className={clsx("tabular-nums text-zinc-100", sizeClass)}>
        {parts.ranking.toFixed(0)}
      </span>
      <span className={bandClass(band)}>{bandLabel}</span>
    </span>
  );
}

/** One-line legend for the recalibrated score bands. */
export function ScanScoreBandLegend({ className }: { className?: string }) {
  const { t } = useTranslation();
  return (
    <p className={clsx("scan-score-band-legend text-secondary", className)} role="note">
      {t.scan.scoreBandLegend
        .replace("{strong}", String(SCAN_SCORE_STRONG_MIN))
        .replace("{watch}", String(SCAN_SCORE_WATCH_MIN))}
    </p>
  );
}
