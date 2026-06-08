"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { V2ScoreResponse } from "@/lib/types";
import { EarningsFromScore } from "./EarningsSetupBlock";
import { PositionSizingBlock } from "./PositionSizingBlock";
import { RecommendationBlock } from "./RecommendationBlock";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import { ValuationBlock } from "./ValuationBlock";

export function Round2Panel({ score }: { score: V2ScoreResponse }) {
  const { t } = useTranslation();

  return (
    <div className="space-y-3">
      {score.recommendation && <RecommendationBlock data={score.recommendation} />}
      {score.valuation && <ValuationBlock data={score.valuation} />}
      <EarningsFromScore score={score} />
      {score.similar_signal && <SimilarSignalBlock data={score.similar_signal} />}
      {score.position_sizing && <PositionSizingBlock sizing={score.position_sizing} />}
      {score.portfolio_impact && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs text-zinc-400">
          {fmt(t.quant.portfolioImpact, {
            beta: score.portfolio_impact.portfolio_beta_impact ?? "—",
            corr: score.portfolio_impact.correlation_with_portfolio ?? "—",
            holdings: score.portfolio_impact.holdings_source ?? t.common.default,
          })}
        </div>
      )}
    </div>
  );
}
