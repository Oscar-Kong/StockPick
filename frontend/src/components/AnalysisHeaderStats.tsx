"use client";

import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { StatTile } from "@/components/ui/StatTile";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";

interface AnalysisHeaderStatsProps {
  price: number;
  changePct1d?: number | null;
  recommendation?: string | null;
  bucketLabel: string;
  score: number;
  riskLevel: string;
  riskLabel: string;
  dataQualityScore?: number | null;
  priceHistoryLastDate?: string | null;
  priceHistoryIsStale?: boolean;
  legacyScore?: number;
  showLegacyDiff?: boolean;
}

function dataQualityTone(score: number): string {
  if (score >= 70) return "text-positive";
  if (score >= 40) return "text-amber-300";
  return "text-red-300";
}

export function AnalysisHeaderStats({
  price,
  changePct1d,
  recommendation,
  bucketLabel,
  score,
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
    riskLevel === "high" ? "text-red-300" : riskLevel === "medium" ? "text-amber-300" : "text-positive";

  const hasChange = changePct1d != null && !Number.isNaN(changePct1d);
  const changeUp = hasChange && changePct1d >= 0;

  const priceFreshnessHint = priceHistoryLastDate
    ? priceHistoryIsStale
      ? t.common.staleData
      : t.analysis.priceHistoryFresh
    : undefined;

  return (
    <div className="analysis-hero">
      <div className="analysis-hero__ambient" aria-hidden />

      <div className="analysis-hero__head">
        <div className="analysis-hero__price-block">
          <span className="analysis-hero__price-label">{t.common.price}</span>
          <div className="analysis-hero__price-row">
            <span className="analysis-hero__price finance-value">${price.toFixed(2)}</span>
            {hasChange && (
              <span
                className={clsx(
                  "analysis-hero__change-pill finance-value",
                  changeUp ? "analysis-hero__change-pill--up" : "analysis-hero__change-pill--down",
                )}
              >
                {changeUp ? "+" : ""}
                {changePct1d.toFixed(1)}%
              </span>
            )}
          </div>
        </div>

        {recommendation && (
          <RecommendationBadge recommendation={recommendation} className="analysis-hero__chip" />
        )}
      </div>

      <div className="analysis-hero__stats stat-tile-grid">
        <StatTile
          label={t.common.score}
          value={<span className="text-buy">{score.toFixed(1)}</span>}
        />
        <StatTile
          label={t.analysis.riskLabel}
          value={<span className={clsx("capitalize", riskTone)}>{riskLabel}</span>}
        />
        <StatTile label={t.common.bucket} value={bucketLabel} />
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
              priceHistoryIsStale ? "analysis-hero__stat--warn" : "analysis-hero__stat--fresh",
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
