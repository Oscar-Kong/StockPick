"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import {
  displayPillars,
  hasDecomposedScores,
  hasInformativePillarBreakdown,
  readScanScoreParts,
  type DisplayPillar,
} from "@/lib/scanScoreDisplay";
import type { StockResult } from "@/lib/types";

function pillarColor(value: number): string {
  if (value >= 70) return "text-emerald-300";
  if (value >= 45) return "text-amber-200";
  return "text-red-300/90";
}

interface ScanScoreBreakdownProps {
  stock: StockResult;
  compact?: boolean;
  className?: string;
}

function SingleScore({
  value,
  title,
  className,
  size = "md",
}: {
  value: number;
  title?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  const sizeClass =
    size === "lg" ? "text-lg font-semibold" : size === "sm" ? "text-xs font-semibold" : "text-sm font-semibold";
  return (
    <span
      className={clsx("tabular-nums text-zinc-100", sizeClass, className)}
      title={title}
    >
      {value.toFixed(0)}
    </span>
  );
}

/** Ranking score in the table; pillar chips only when they differ from neutral defaults. */
export function ScanScoreBreakdown({ stock, compact, className }: ScanScoreBreakdownProps) {
  const { t } = useTranslation();
  const parts = readScanScoreParts(stock);
  const informative = hasInformativePillarBreakdown(parts);
  const pillars = displayPillars(parts);

  if (!hasDecomposedScores(stock)) {
    return <SingleScore value={parts.ranking} className={className} size={compact ? "sm" : "md"} />;
  }

  // Confidence/tradability stuck at ~50 — show one composite score (no noisy pillar row).
  if (!informative) {
    return (
      <SingleScore
        value={parts.ranking}
        title={t.scan.rankingScoreOnlyHint}
        className={className}
        size={compact ? "sm" : "lg"}
      />
    );
  }

  const pillarLabels: Record<DisplayPillar["key"], string> = {
    alpha: t.scan.pillarAlpha,
    confidence: t.scan.pillarConfidence,
    trade: t.scan.pillarTradability,
  };

  if (compact) {
    return (
      <div className={clsx("scan-score-breakdown scan-score-breakdown--compact", className)}>
        <SingleScore value={parts.ranking} title={t.scan.rankingScore} size="sm" />
        {pillars.length > 0 && (
          <div className="scan-score-breakdown__pillars">
            {pillars.map((item) => (
              <div key={item.key} className="scan-score-breakdown__pillar" title={pillarLabels[item.key]}>
                <span className="scan-score-breakdown__pillar-label">{pillarLabels[item.key]}</span>
                <span className={clsx("scan-score-breakdown__pillar-value tabular-nums", pillarColor(item.value))}>
                  {item.value.toFixed(0)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className={clsx("scan-score-breakdown", className)}>
      <div className="scan-score-breakdown__rank" title={t.scan.rankingScore}>
        <span className="text-[10px] uppercase tracking-wide text-zinc-500">{t.scan.rankingScore}</span>
        <SingleScore value={parts.ranking} size="lg" />
      </div>
      {pillars.length > 0 && (
        <div className="scan-score-breakdown__pillars">
          {pillars.map((item) => (
            <div key={item.key} className="scan-score-breakdown__pillar" title={pillarLabels[item.key]}>
              <span className="scan-score-breakdown__pillar-label">{pillarLabels[item.key]}</span>
              <span className={clsx("scan-score-breakdown__pillar-value tabular-nums", pillarColor(item.value))}>
                {item.value.toFixed(0)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
