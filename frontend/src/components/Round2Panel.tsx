"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { V2ScoreResponse } from "@/lib/types";
import { EarningsFromScore } from "./EarningsSetupBlock";
import { PositionSizingBlock } from "./PositionSizingBlock";
import { RecommendationBlock } from "./RecommendationBlock";
import { ScoreSourceBadge } from "./ScoreSourceBadge";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import { ValuationBlock } from "./ValuationBlock";

interface Round2PanelProps {
  score: V2ScoreResponse;
  /** Overview shows recommendation context only — score lives in the hero bar. */
  variant?: "full" | "overview";
}

export function Round2Panel({ score, variant = "full" }: Round2PanelProps) {
  const { t } = useTranslation();

  if (variant === "overview") {
    return (
      <div className="space-y-2.5">
        {score.market_regime && (
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t.analysis.marketRegime}:{" "}
            <span className="capitalize text-zinc-300">{score.market_regime}</span>
          </p>
        )}
        {score.recommendation ? (
          <RecommendationBlock data={score.recommendation} />
        ) : (
          <p className="text-sm text-secondary">{score.summary ?? t.analysis.summary}</p>
        )}
        {score.portfolio_impact && (
          <p className="text-xs leading-relaxed text-zinc-500">
            {fmt(t.quant.portfolioImpact, {
              beta: score.portfolio_impact.portfolio_beta_impact ?? "—",
              corr: score.portfolio_impact.correlation_with_portfolio ?? "—",
              holdings: score.portfolio_impact.holdings_source ?? t.common.default,
            })}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2">
        <span className="text-lg font-semibold tabular-nums text-zinc-50">{score.score.toFixed(1)}</span>
        <span className="text-xs text-zinc-500">{t.analysis.scoreChip}</span>
        <ScoreSourceBadge source="scoring_engine_v2" />
        {score.market_regime && (
          <span className="chip px-1.5 py-0.5 text-xs capitalize text-zinc-400">{score.market_regime}</span>
        )}
      </div>
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
