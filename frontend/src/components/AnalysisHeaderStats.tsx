"use client";

import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { StatTile } from "@/components/ui/StatTile";
import { useTranslation } from "@/lib/i18n";
import type { ScoreSource } from "@/lib/v2Score";
import clsx from "clsx";

interface AnalysisHeaderStatsProps {
  price: number;
  changePct1d?: number | null;
  recommendation?: string | null;
  bucketLabel: string;
  score: number;
  scoreSource: ScoreSource;
  riskLevel: string;
  riskLabel: string;
  dataQualityScore?: number | null;
  priceHistoryLastDate?: string | null;
  priceHistoryIsStale?: boolean;
  legacyScore?: number;
  showLegacyDiff?: boolean;
}

function dataQualityTone(score: number): string {
  if (score >= 70) return "text-brand";
  if (score >= 40) return "text-amber-300";
  return "text-red-300";
}

function scoreSourceTone(source: ScoreSource): string {
  return source === "scoring_engine_v2" ? "text-emerald-300" : "text-secondary";
}

export function AnalysisHeaderStats({
  price,
  changePct1d,
  recommendation,
  bucketLabel,
  score,
  scoreSource,
  riskLevel,
  riskLabel,
  dataQualityScore,
  priceHistoryLastDate,
  priceHistoryIsStale,
  legacyScore,
  showLegacyDiff,
}: AnalysisHeaderStatsProps) {
  const { t } = useTranslation();

  const riskTone =
    riskLevel === "high" ? "text-red-300" : riskLevel === "medium" ? "text-amber-300" : "text-brand";

  const changeTone =
    changePct1d == null || Number.isNaN(changePct1d)
      ? "text-secondary"
      : changePct1d >= 0
        ? "text-brand"
        : "text-negative";

  const priceFreshnessHint = priceHistoryLastDate
    ? priceHistoryIsStale
      ? t.common.staleData
      : t.analysis.priceHistoryFresh
    : undefined;

  const scoreSourceLabel =
    scoreSource === "scoring_engine_v2"
      ? t.analysis.scoreSourceV2Short
      : t.analysis.scoreSourceLegacyShort;

  return (
    <div className="analysis-hero">
      <div className="analysis-hero__price-row">
        <span className="analysis-hero__price finance-value">${price.toFixed(2)}</span>
        {changePct1d != null && !Number.isNaN(changePct1d) && (
          <span className={clsx("analysis-hero__change finance-value", changeTone)}>
            {changePct1d >= 0 ? "+" : ""}
            {changePct1d.toFixed(1)}%
          </span>
        )}
        {recommendation && (
          <RecommendationBadge recommendation={recommendation} className="analysis-hero__chip" />
        )}
      </div>

      <div className="analysis-hero__stats stat-tile-grid">
        <StatTile label={t.common.score} value={score.toFixed(1)} />
        <StatTile
          label={t.analysis.riskLabel}
          value={<span className={clsx("capitalize", riskTone)}>{riskLabel}</span>}
        />
        <StatTile label={t.common.bucket} value={bucketLabel} />
        <StatTile
          label={t.analysis.scoreSourceShortLabel}
          value={<span className={scoreSourceTone(scoreSource)}>{scoreSourceLabel}</span>}
          tooltip={t.analysis.scoreSourceHint}
        />
        {dataQualityScore != null && (
          <StatTile
            label={t.analysis.dataQualityShortLabel}
            value={
              <span className={dataQualityTone(dataQualityScore)}>
                {dataQualityScore.toFixed(0)}%
              </span>
            }
          />
        )}
        {priceHistoryLastDate && (
          <StatTile
            label={t.analysis.latestBarLabel}
            value={priceHistoryLastDate}
            hint={priceFreshnessHint}
            className={clsx(
              priceHistoryIsStale ? "analysis-hero__stat--warn" : "analysis-hero__stat--fresh"
            )}
          />
        )}
        {showLegacyDiff && legacyScore != null && (
          <StatTile
            label={t.analysis.legacyScoreShort}
            value={legacyScore.toFixed(1)}
            className="text-secondary"
          />
        )}
      </div>
    </div>
  );
}
