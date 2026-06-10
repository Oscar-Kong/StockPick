"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { isFeatureDisabledError, parseApiError } from "@/lib/apiError";
import { getV2FeedbackSummary, getV2Predictions } from "@/lib/api";
import type { FeedbackSummaryResponse, PredictionSnapshotItem } from "@/lib/types";
import {
  arePredictionOutcomesStale,
  countResolvedPredictions,
  countUnresolvedPredictions,
  isPredictionResolved,
  predictionReturnPct,
} from "@/lib/predictions";
import { useTranslation, useTRef } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

export function HomePredictionCard() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [predictions, setPredictions] = useState<PredictionSnapshotItem[]>([]);
  const [feedback, setFeedback] = useState<FeedbackSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDisabled(false);
    try {
      const [pred, fb] = await Promise.allSettled([
        getV2Predictions({ limit: 20 }),
        getV2FeedbackSummary(),
      ]);
      if (pred.status === "fulfilled") {
        setPredictions(pred.value.predictions ?? []);
      } else {
        setPredictions([]);
        const msg = parseApiError(pred.reason, tRef.current.home.predictionsFailed);
        if (isFeatureDisabledError(msg)) setDisabled(true);
        else setError(msg);
      }
      if (fb.status === "fulfilled") setFeedback(fb.value);
      else setFeedback(null);
    } catch (e) {
      setError(parseApiError(e, tRef.current.home.predictionsFailed));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const unresolved = countUnresolvedPredictions(predictions);
  const resolved = countResolvedPredictions(predictions);
  const latestResolved = predictions.find(isPredictionResolved);
  const stale = arePredictionOutcomesStale(predictions, feedback);

  return (
    <section className="surface-card p-4">
      <SectionHeader
        title={t.home.predictionsTitle}
        subtitle={t.home.predictionsSubtitle}
        action={
          <Link href="/quant-lab?tab=predictions" className="text-xs text-[#7dff8e] hover:underline">
            {t.home.openPredictions}
          </Link>
        }
      />
      {loading && <LoadingSkeleton lines={2} />}
      {!loading && disabled && (
        <p className="text-xs text-zinc-500">{t.home.predictionsDisabled}</p>
      )}
      {!loading && !disabled && error && (
        <ErrorState message={error} onRetry={() => void load()} />
      )}
      {!loading && !disabled && !error && (
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <dt className="text-xs text-zinc-500">{t.home.unresolvedPredictions}</dt>
            <dd className="text-xl font-semibold tabular-nums text-amber-200">{unresolved}</dd>
          </div>
          <div>
            <dt className="text-xs text-zinc-500">{t.home.resolvedRecent}</dt>
            <dd className="text-xl font-semibold tabular-nums text-[#7dff8e]">{resolved}</dd>
          </div>
        </dl>
      )}
      {stale && !loading && !disabled && (
        <p className="mt-2 text-xs text-amber-300/90">{t.home.outcomesStale}</p>
      )}
      {latestResolved && !loading && !disabled && (
        <p className="mt-2 text-xs text-zinc-500">
          {t.home.latestOutcome}: {latestResolved.symbol}{" "}
          {(() => {
            const ret = predictionReturnPct(latestResolved, 60);
            return ret != null ? `${ret.toFixed(1)}%` : "—";
          })()}
        </p>
      )}
    </section>
  );
}
