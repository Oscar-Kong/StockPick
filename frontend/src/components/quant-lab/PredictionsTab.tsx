"use client";

import { getV2FeedbackSummary, getV2Predictions } from "@/lib/api";
import { isFeatureDisabledError, parseApiError } from "@/lib/apiError";
import {
  arePredictionOutcomesStale,
  countResolvedPredictions,
  countUnresolvedPredictions,
  formatScore,
  isPredictionResolved,
  predictionDisplayScore,
  predictionReturnPct,
} from "@/lib/predictions";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";
import { computePredictionsReliability } from "@/lib/researchReliability";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import { ResearchReliabilityCard } from "./ResearchReliabilityCard";
import {
  QuantLabEmptyState,
  QuantLabTabLayout,
  StaleDataBadge,
  TabRefreshRow,
} from "./QuantLabTabShell";

export function PredictionsTab() {
  const { t } = useTranslation();
  const [predictions, setPredictions] = useState<Awaited<ReturnType<typeof getV2Predictions>>["predictions"]>([]);
  const [feedback, setFeedback] = useState<Awaited<ReturnType<typeof getV2FeedbackSummary>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [predictionsError, setPredictionsError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setPredictionsError(null);
    setFeedbackError(null);
    setDisabled(false);

    const [p, f] = await Promise.allSettled([getV2Predictions({ limit: 50 }), getV2FeedbackSummary()]);

    if (p.status === "fulfilled") {
      setPredictions(p.value.predictions ?? []);
    } else {
      setPredictions([]);
      const msg = parseApiError(p.reason, t.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) setDisabled(true);
      else setPredictionsError(msg);
    }

    if (f.status === "fulfilled") {
      setFeedback(f.value);
    } else {
      setFeedback(null);
      const msg = parseApiError(f.reason, t.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) setDisabled(true);
      else setFeedbackError(msg);
    }

    setLoading(false);
  }, [t.quantLab.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const unresolved = countUnresolvedPredictions(predictions);
  const resolved = countResolvedPredictions(predictions);
  const stale = arePredictionOutcomesStale(predictions, feedback);
  const hasAnyData = predictions.length > 0 || feedback != null;
  const reliability = useMemo(
    () => computePredictionsReliability({ predictions, feedback, disabled, loading }),
    [predictions, feedback, disabled, loading]
  );

  return (
    <QuantLabTabLayout
      title={t.quantLab.tabPredictions}
      description={
        <TooltipLabel label={t.quantLab.hintPredictions} tooltip={t.product.predictionOutcomeTooltip} />
      }
      reliability={<ResearchReliabilityCard score={reliability} />}
      statusBadge={
        <>
          <ResearchOnlyBadge tooltip={t.product.predictionOutcomeTooltip} />
          {stale && !loading && !disabled ? <StaleDataBadge /> : null}
        </>
      }
      controls={<TabRefreshRow onRefresh={() => void load()} />}
      loading={loading}
      disabled={disabled}
      disabledMessage={t.quantLab.predictionsDisabled}
      partialWarning={
        !disabled && !loading
          ? [predictionsError, feedbackError].filter(Boolean).join(" · ") || null
          : null
      }
    >
      {!disabled && (
        <>
          {stale && <p className="text-xs text-amber-300">{t.home.outcomesStale}</p>}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-zinc-500">{t.home.unresolvedPredictions}</dt>
              <dd className="text-lg font-semibold tabular-nums text-amber-200">{unresolved}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.home.resolvedRecent}</dt>
              <dd className="text-lg font-semibold tabular-nums text-[#7dff8e]">{resolved}</dd>
            </div>
            {feedback && (
              <>
                <div>
                  <dt className="text-xs text-zinc-500">{t.quantLab.tradeOutcomes}</dt>
                  <dd className="text-lg font-semibold tabular-nums">{feedback.outcomes_count ?? 0}</dd>
                </div>
                <div>
                  <dt className="text-xs text-zinc-500">{t.quantLab.meanForecastError}</dt>
                  <dd className="text-lg font-semibold tabular-nums">
                    {feedback.mean_prediction_error_pct != null &&
                    Number.isFinite(feedback.mean_prediction_error_pct)
                      ? `${feedback.mean_prediction_error_pct.toFixed(2)}%`
                      : "—"}
                  </dd>
                </div>
              </>
            )}
          </dl>
          {!hasAnyData && !predictionsError && !feedbackError ? (
            <QuantLabEmptyState message={t.quantLab.noPredictions} />
          ) : predictions.length === 0 && predictionsError ? (
            <QuantLabEmptyState message={t.quantLab.noPredictions} />
          ) : predictions.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-xs">
                <thead>
                  <tr className="text-left text-zinc-500">
                    <th className="py-1 pr-2">{t.common.symbol}</th>
                    <th className="py-1 pr-2">{t.quantLab.alphaScore}</th>
                    <th className="py-1 pr-2">{t.quantLab.recommendation}</th>
                    <th className="py-1 pr-2">{t.quantLab.return60d}</th>
                    <th className="py-1">{t.quantLab.resolved}</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.slice(0, 20).map((p, index) => {
                    const ret = predictionReturnPct(p, 60);
                    return (
                      <tr key={p.id ?? `pred-${index}`} className="border-t border-zinc-900">
                        <td className="py-2 pr-2">{p.symbol ?? "—"}</td>
                        <td className="py-2 pr-2 tabular-nums">{formatScore(predictionDisplayScore(p))}</td>
                        <td className="py-2 pr-2 capitalize text-zinc-400">{p.recommendation ?? "—"}</td>
                        <td className="py-2 pr-2 tabular-nums">
                          {ret != null && Number.isFinite(ret) ? `${ret.toFixed(1)}%` : "—"}
                        </td>
                        <td className="py-2">{isPredictionResolved(p) ? t.common.yes : t.common.no}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </QuantLabTabLayout>
  );
}
