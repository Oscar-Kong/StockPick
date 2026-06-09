"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { ScanParitySummary } from "@/lib/types";
import type { ScoreSource } from "@/lib/v2Score";
import { TooltipLabel } from "./ui/TooltipLabel";
import { ScoreSourceBadge } from "./ScoreSourceBadge";

interface ScanScoreMetaProps {
  scoringEngineUsed?: boolean | null;
  paritySummary?: ScanParitySummary | null;
}

export function ScanScoreMeta({ scoringEngineUsed, paritySummary }: ScanScoreMetaProps) {
  const { t } = useTranslation();

  if (scoringEngineUsed == null && !paritySummary) {
    return null;
  }

  const source: ScoreSource = scoringEngineUsed ? "scoring_engine_v2" : "legacy_screener";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <ScoreSourceBadge source={source} />
      {paritySummary &&
        (paritySummary.average_delta != null || paritySummary.max_delta != null) && (
          <TooltipLabel
            label={fmt(t.scan.paritySummary, {
              avg: paritySummary.average_delta?.toFixed(1) ?? "—",
              max: paritySummary.max_delta?.toFixed(1) ?? "—",
              diffs: String(paritySummary.recommendation_bucket_diffs ?? 0),
            })}
            tooltip={t.product.parityDeltaTooltip}
            className="chip px-2 py-1 text-[10px] tabular-nums text-zinc-500"
          />
        )}
    </div>
  );
}
