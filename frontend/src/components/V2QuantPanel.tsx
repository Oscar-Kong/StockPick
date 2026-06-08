"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import type { V2ScoreResponse } from "@/lib/types";
import { safeAttribution, safeRiskBreakdown, factorsToSignals } from "@/lib/v2Score";
import { ScoreBreakdown } from "./ScoreBreakdown";

interface V2QuantPanelProps {
  score: V2ScoreResponse;
}

export function V2QuantPanel({ score }: V2QuantPanelProps) {
  const { t } = useTranslation();
  const attribution = safeAttribution(score);
  const risk = safeRiskBreakdown(score);
  const signals = factorsToSignals(score);

  return (
    <div className="space-y-4">
      <div className="analysis-block">
        <h3 className="label-caps mb-2">{t.analysis.factorAttribution}</h3>
        <ScoreBreakdown signals={signals} className="analysis-chart-box h-80 w-full p-3" />
      </div>

      {attribution && (
        <div className="analysis-block">
          <h3 className="label-caps mb-2">{t.analysis.scorePipeline}</h3>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
            <div>
              <dt className="text-zinc-500">{t.analysis.rawScore}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{attribution.raw_score.toFixed(1)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.analysis.regimeMult}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{attribution.regime_mult.toFixed(3)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.analysis.dqMult}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{attribution.dq_multiplier.toFixed(3)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.analysis.riskDeduction}</dt>
              <dd className="font-semibold tabular-nums text-zinc-100">{attribution.risk_deduction.toFixed(1)}</dd>
            </div>
            <div>
              <dt className="text-zinc-500">{t.analysis.finalScore}</dt>
              <dd className="font-semibold tabular-nums text-[#7dff8e]">{attribution.final_score.toFixed(1)}</dd>
            </div>
            {score.market_regime && (
              <div>
                <dt className="text-zinc-500">{t.analysis.marketRegime}</dt>
                <dd className="font-semibold capitalize text-zinc-100">{score.market_regime}</dd>
              </div>
            )}
          </dl>
        </div>
      )}

      {risk && (
        <div className="analysis-block">
          <h3 className="label-caps mb-2">{t.analysis.riskBreakdown}</h3>
          <div className="mb-2 flex flex-wrap gap-3 text-xs">
            <span className="text-zinc-400">
              {fmt(t.analysis.riskIndex, { value: risk.risk_score.toFixed(0) })}
            </span>
            <span className="text-zinc-400">
              {fmt(t.analysis.riskDeductionPts, { value: risk.deduction_pts.toFixed(1) })}
            </span>
          </div>
          {risk.items.length > 0 ? (
            <ul className="space-y-1 text-xs text-zinc-400">
              {risk.items.slice(0, 6).map((item, idx) => (
                <li key={idx} className="rounded border border-zinc-800/80 px-2 py-1">
                  {typeof item.label === "string" ? item.label : JSON.stringify(item)}
                  {typeof item.points === "number" ? ` (−${item.points})` : ""}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-zinc-500">{t.analysis.noRiskItems}</p>
          )}
        </div>
      )}
    </div>
  );
}
