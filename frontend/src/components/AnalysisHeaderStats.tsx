"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StatTile } from "@/components/ui/StatTile";
import { useTranslation } from "@/lib/i18n";
import type { ScoreSource } from "@/lib/v2Score";
import clsx from "clsx";

interface AnalysisHeaderStatsProps {
  price: number;
  bucketLabel: string;
  score: number;
  scoreSource: ScoreSource;
  riskLevel: string;
  riskLabel: string;
  legacyScore?: number;
  showLegacyDiff?: boolean;
}

export function AnalysisHeaderStats({
  price,
  bucketLabel,
  score,
  scoreSource,
  riskLevel,
  riskLabel,
  legacyScore,
  showLegacyDiff,
}: AnalysisHeaderStatsProps) {
  const { t } = useTranslation();

  const riskTone =
    riskLevel === "high"
      ? "text-red-300"
      : riskLevel === "medium"
        ? "text-amber-300"
        : "text-[#7dff8e]";

  return (
    <dl className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
      <StatTile
        label={t.common.price}
        value={<span className="tabular-nums">${price.toFixed(2)}</span>}
      />
      <StatTile label={t.common.bucket} value={bucketLabel} />
      <StatTile
        label={t.common.score}
        tooltip={t.analysis.scoreSourceHint}
        value={<span className="tabular-nums">{score.toFixed(1)}</span>}
      />
      <StatTile
        label={t.analysis.scoreSourceLabel}
        tooltip={t.analysis.scoreSourceHint}
        value={<ScoreSourceBadge source={scoreSource} />}
      />
      <StatTile
        label={t.analysis.riskLabel}
        value={<span className={clsx("capitalize", riskTone)}>{riskLabel}</span>}
      />
      {showLegacyDiff && legacyScore != null && (
        <StatTile
          label={t.analysis.legacyScoreShort}
          tooltip={t.analysis.legacyScoreHint}
          value={<span className="tabular-nums text-zinc-400">{legacyScore.toFixed(1)}</span>}
          className="sm:col-span-2 xl:col-span-1"
        />
      )}
    </dl>
  );
}
