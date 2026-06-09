"use client";

import { QuantHealthCard } from "@/components/quant/QuantHealthCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ResearchWarning } from "@/components/ui/ResearchWarning";
import { TooltipLabel } from "@/components/ui/TooltipLabel";
import { isFeatureDisabledError, parseApiError } from "@/lib/apiError";
import {
  getSchedulerStatus,
  getV2Audit,
  getV2FactorPerformance,
  getV2FactorsAdmin,
  getV2FeedbackSummary,
  getV2Predictions,
  getV2SleeveWeights,
  getV2Version,
  runPairsResearch,
  runWalkForwardResearch,
} from "@/lib/api";
import {
  arePredictionOutcomesStale,
  countResolvedPredictions,
  countUnresolvedPredictions,
  formatScore,
  isPredictionResolved,
  predictionDisplayScore,
  predictionReturnPct,
} from "@/lib/predictions";
import type { Bucket } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useState } from "react";

function FeatureDisabledNotice({ message }: { message: string }) {
  return <p className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-zinc-400">{message}</p>;
}

export function FactorPerformanceTab() {
  const { t } = useTranslation();
  const [data, setData] = useState<Awaited<ReturnType<typeof getV2FactorPerformance>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [sleeve, setSleeve] = useState<Bucket>("medium");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDisabled(false);
    try {
      setData(await getV2FactorPerformance({ sleeve }));
    } catch (e) {
      const msg = parseApiError(e, t.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) {
        setDisabled(true);
        setData(null);
      } else {
        setError(msg);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [sleeve, t.quantLab.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const factors = data?.factors ?? [];
  const showStaleWarning = !loading && !error && !disabled && !data?.as_of_date;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-zinc-500">
          {t.common.bucket}
          <select
            value={sleeve}
            onChange={(e) => setSleeve(e.target.value as Bucket)}
            className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
          >
            <option value="penny">penny</option>
            <option value="medium">medium</option>
            <option value="compounder">compounder</option>
          </select>
        </label>
        {showStaleWarning && (
          <span className="text-xs text-amber-300">{t.quantLab.staleIcWarning}</span>
        )}
      </div>
      {loading && <LoadingSkeleton lines={5} />}
      {disabled && <FeatureDisabledNotice message={t.quantLab.featureDisabled} />}
      {error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && !disabled && data && (
        <>
          <p className="text-xs text-zinc-500">
            {t.quantLab.icAsOf}: {data.as_of_date ?? "—"}
          </p>
          {factors.length === 0 ? (
            <EmptyState message={t.quantLab.noFactorIc} />
          ) : (
            factors.slice(0, 12).map((f) => {
              const h = Object.values(f.horizons)[0];
              if (!h) return null;
              return (
                <div key={f.factor_id} className="rounded-lg border border-zinc-800 p-3 text-xs">
                  <div className="flex justify-between gap-3">
                    <span className="font-medium text-zinc-200">{f.factor_id}</span>
                    <span className="tabular-nums text-zinc-400">
                      IC {h.ic?.toFixed(3) ?? "—"} · n={h.sample_n ?? "—"}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </>
      )}
    </div>
  );
}

export function WalkForwardTab() {
  const { t } = useTranslation();
  const [sleeve, setSleeve] = useState<Bucket>("medium");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runWalkForwardResearch>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      const end = new Date();
      const start = new Date(end);
      start.setFullYear(start.getFullYear() - 2);
      const res = await runWalkForwardResearch({
        sleeve,
        start_date: start.toISOString().slice(0, 10),
        end_date: end.toISOString().slice(0, 10),
        forward_horizons: [20, 60],
        max_symbols: 25,
      });
      setResult(res);
    } catch (e) {
      setError(parseApiError(e, t.quantLab.runFailed));
    } finally {
      setRunning(false);
    }
  };

  const horizonRows = result?.aggregate_horizons
    ? Object.entries(result.aggregate_horizons)
    : [];

  return (
    <div className="space-y-4">
      <ResearchWarning message={t.quantLab.walkForwardOfflineWarning} />
      <div className="flex flex-wrap gap-2">
        <select
          value={sleeve}
          onChange={(e) => setSleeve(e.target.value as Bucket)}
          className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
        >
          <option value="penny">penny</option>
          <option value="medium">medium</option>
          <option value="compounder">compounder</option>
        </select>
        <button type="button" onClick={() => void run()} disabled={running} className="btn-primary px-3 py-1.5 text-sm">
          {running ? t.common.running : t.quantLab.runWalkForward}
        </button>
      </div>
      {error && <ErrorState message={error} onRetry={() => void run()} />}
      {result && (
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.runStatus}</dt>
              <dd>{result.status}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.periodsScored}</dt>
              <dd>{result.periods_scored}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.meanTurnover}</dt>
              <dd>{result.mean_turnover?.toFixed(3) ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-xs text-zinc-500">{t.quantLab.runId}</dt>
              <dd className="truncate font-mono text-xs">{result.run_id}</dd>
            </div>
          </dl>
          {horizonRows.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-medium text-zinc-400">{t.quantLab.aggregateHorizons}</h4>
              <ul className="space-y-1 text-xs text-zinc-500">
                {horizonRows.map(([horizon, stats]) => (
                  <li key={horizon}>
                    {horizon}d:{" "}
                    {typeof stats === "object" && stats != null
                      ? JSON.stringify(stats)
                      : String(stats)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {result.periods_scored === 0 && (
            <EmptyState message={t.quantLab.walkForwardNoPeriods} />
          )}
        </div>
      )}
    </div>
  );
}

export function PredictionsTab() {
  const { t } = useTranslation();
  const [predictions, setPredictions] = useState<Awaited<ReturnType<typeof getV2Predictions>>["predictions"]>([]);
  const [feedback, setFeedback] = useState<Awaited<ReturnType<typeof getV2FeedbackSummary>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [partialError, setPartialError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setPartialError(null);
    setDisabled(false);
    const [p, f] = await Promise.allSettled([getV2Predictions({ limit: 50 }), getV2FeedbackSummary()]);
    let failed = 0;

    if (p.status === "fulfilled") {
      setPredictions(p.value.predictions ?? []);
    } else {
      setPredictions([]);
      const msg = parseApiError(p.reason, t.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) setDisabled(true);
      else {
        failed += 1;
        setError(msg);
      }
    }

    if (f.status === "fulfilled") {
      setFeedback(f.value);
    } else {
      setFeedback(null);
      const msg = parseApiError(f.reason, t.quantLab.loadFailed);
      if (isFeatureDisabledError(msg)) setDisabled(true);
      else if (failed === 0) setPartialError(msg);
    }

    setLoading(false);
  }, [t.quantLab.loadFailed]);

  useEffect(() => {
    void load();
  }, [load]);

  const unresolved = countUnresolvedPredictions(predictions);
  const resolved = countResolvedPredictions(predictions);
  const stale = arePredictionOutcomesStale(predictions, feedback);

  return (
    <div className="space-y-4">
      {loading && <LoadingSkeleton lines={4} />}
      {disabled && <FeatureDisabledNotice message={t.quantLab.predictionsDisabled} />}
      {error && !disabled && <ErrorState message={error} onRetry={() => void load()} />}
      {partialError && !error && !disabled && (
        <p className="text-xs text-amber-300">{partialError}</p>
      )}
      {!loading && !disabled && !error && (
        <>
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
                  <dd className="text-lg font-semibold tabular-nums">{feedback.outcomes_count}</dd>
                </div>
                <div>
                  <dt className="text-xs text-zinc-500">{t.quantLab.meanForecastError}</dt>
                  <dd className="text-lg font-semibold tabular-nums">
                    {feedback.mean_prediction_error_pct != null
                      ? `${feedback.mean_prediction_error_pct.toFixed(2)}%`
                      : "—"}
                  </dd>
                </div>
              </>
            )}
          </dl>
          {stale && <p className="text-xs text-amber-300">{t.home.outcomesStale}</p>}
          {predictions.length === 0 ? (
            <EmptyState message={t.quantLab.noPredictions} />
          ) : (
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
                  {predictions.slice(0, 20).map((p) => (
                    <tr key={p.id} className="border-t border-zinc-900">
                      <td className="py-2 pr-2">{p.symbol}</td>
                      <td className="py-2 pr-2 tabular-nums">{formatScore(predictionDisplayScore(p))}</td>
                      <td className="py-2 pr-2 capitalize text-zinc-400">{p.recommendation ?? "—"}</td>
                      <td className="py-2 pr-2 tabular-nums">
                        {(() => {
                          const ret = predictionReturnPct(p, 60);
                          return ret != null ? `${ret.toFixed(1)}%` : "—";
                        })()}
                      </td>
                      <td className="py-2">{isPredictionResolved(p) ? t.common.yes : t.common.no}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function PairsTab() {
  const { t } = useTranslation();
  const [symbols, setSymbols] = useState("AAPL, MSFT, GOOGL");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<Awaited<ReturnType<typeof runPairsResearch>> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const run = async () => {
    setValidationError(null);
    setError(null);
    const list = symbols
      .split(/[\s,]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (list.length < 2) {
      setValidationError(t.quantLab.pairsMinSymbols);
      return;
    }

    setRunning(true);
    try {
      setResult(await runPairsResearch({ symbols: list, lookback_period: "1y" }));
    } catch (e) {
      setResult(null);
      setError(parseApiError(e, t.quantLab.runFailed));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-4">
      <ResearchWarning />
      <p className="text-xs text-zinc-500">
        <TooltipLabel label={t.quantLab.tabPairs} tooltip={t.quantLab.cointegrationTooltip} />
      </p>
      <textarea
        value={symbols}
        onChange={(e) => setSymbols(e.target.value)}
        rows={2}
        className="w-full rounded-lg border border-zinc-700 bg-zinc-950 p-2 text-sm"
      />
      <button type="button" onClick={() => void run()} disabled={running} className="btn-primary px-3 py-1.5 text-sm">
        {running ? t.common.running : t.quantLab.runPairs}
      </button>
      {validationError && <p className="text-xs text-amber-300">{validationError}</p>}
      {error && <ErrorState message={error} onRetry={() => void run()} />}
      {result && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">
            {t.quantLab.pairsSummary}: {result.pairs_returned}/{result.pairs_evaluated} ·{" "}
            {t.quantLab.cointegrated}: {result.cointegrated_count}
            {!result.statsmodels_available && ` · ${t.quantLab.statsmodelsMissing}`}
          </p>
          {result.notes?.length > 0 && (
            <ul className="list-inside list-disc text-xs text-zinc-500">
              {result.notes.map((note, i) => (
                <li key={i}>{note}</li>
              ))}
            </ul>
          )}
          {result.pairs.length === 0 ? (
            <EmptyState message={t.quantLab.noPairs} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[480px] text-xs">
                <thead>
                  <tr className="text-left text-zinc-500">
                    <th className="py-1 pr-2">{t.quantLab.pair}</th>
                    <th className="py-1 pr-2">p</th>
                    <th className="py-1 pr-2">z</th>
                    <th className="py-1">{t.quantLab.pairStatus}</th>
                  </tr>
                </thead>
                <tbody>
                  {result.pairs.slice(0, 15).map((p) => (
                    <tr key={`${p.symbol_x}-${p.symbol_y}`} className="border-t border-zinc-900">
                      <td className="py-2 pr-2">
                        {p.symbol_x}/{p.symbol_y}
                      </td>
                      <td className="py-2 pr-2 tabular-nums">{p.p_value?.toFixed(4) ?? "—"}</td>
                      <td className="py-2 pr-2 tabular-nums">{p.latest_z_score?.toFixed(2) ?? "—"}</td>
                      <td className="py-2 text-zinc-400">
                        {p.sufficient === false
                          ? p.warning ?? t.quantLab.insufficientData
                          : p.cointegrated_5pct
                            ? t.quantLab.cointegrated
                            : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function DataQualityTab() {
  return (
    <div className="space-y-4">
      <QuantHealthCard embedded />
      <SchedulerPanel />
    </div>
  );
}

function SchedulerPanel() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Awaited<ReturnType<typeof getSchedulerStatus>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getSchedulerStatus()
      .then(setStatus)
      .catch((e) => {
        setStatus(null);
        setError(parseApiError(e, t.settings.schedulerUnavailable));
      })
      .finally(() => setLoading(false));
  }, [t.settings.schedulerUnavailable]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <LoadingSkeleton lines={2} />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!status) return <p className="text-xs text-zinc-500">{t.settings.schedulerUnavailable}</p>;

  return (
    <div className="surface-card p-4">
      <h3 className="text-sm font-semibold text-zinc-200">{t.settings.schedulerTitle}</h3>
      <p className="mt-1 text-xs text-zinc-500">
        {status.enabled ? t.settings.schedulerOn : t.settings.schedulerOff}
      </p>
      {status.recent_jobs.length === 0 ? (
        <p className="mt-2 text-xs text-zinc-500">{t.quantLab.noSchedulerJobs}</p>
      ) : (
        <ul className="mt-2 space-y-1 text-xs text-zinc-400">
          {status.recent_jobs.slice(0, 5).map((j, i) => (
            <li key={`${j.job_name}-${i}`}>
              {j.job_name}: {j.status} {j.message ? `— ${j.message}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ModelAdminTab() {
  const { t } = useTranslation();
  const [version, setVersion] = useState<Record<string, unknown> | null>(null);
  const [weights, setWeights] = useState<Awaited<ReturnType<typeof getV2SleeveWeights>> | null>(null);
  const [audit, setAudit] = useState<Awaited<ReturnType<typeof getV2Audit>> | null>(null);
  const [factorsAdmin, setFactorsAdmin] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<string[]>([]);
  const [disabled, setDisabled] = useState(false);

  useEffect(() => {
    Promise.allSettled([
      getV2Version(),
      getV2SleeveWeights("medium"),
      getV2Audit({ limit: 10 }),
      getV2FactorsAdmin("medium"),
    ]).then(([v, w, a, fa]) => {
      const nextErrors: string[] = [];

      if (v.status === "fulfilled") setVersion(v.value);
      else {
        const msg = parseApiError(v.reason);
        if (isFeatureDisabledError(msg)) setDisabled(true);
        else nextErrors.push(msg);
      }

      if (w.status === "fulfilled") setWeights(w.value);
      else if (!isFeatureDisabledError(parseApiError(w.reason))) nextErrors.push(parseApiError(w.reason));

      if (a.status === "fulfilled") setAudit(a.value);
      else if (!isFeatureDisabledError(parseApiError(a.reason))) nextErrors.push(parseApiError(a.reason));

      if (fa.status === "fulfilled") setFactorsAdmin(fa.value);
      else if (!isFeatureDisabledError(parseApiError(fa.reason))) nextErrors.push(parseApiError(fa.reason));

      setErrors(nextErrors);
      setLoading(false);
    });
  }, []);

  if (loading) return <LoadingSkeleton lines={4} />;

  const factorCount = Array.isArray(factorsAdmin?.factors) ? factorsAdmin.factors.length : null;
  const hasContent = version || weights || audit || factorsAdmin;

  return (
    <div className="space-y-4 text-sm">
      {disabled && <FeatureDisabledNotice message={t.quantLab.featureDisabled} />}
      {errors.length > 0 && (
        <ul className="space-y-1 text-xs text-amber-300">
          {errors.map((msg, i) => (
            <li key={i}>{msg}</li>
          ))}
        </ul>
      )}
      {!hasContent && !disabled && (
        <EmptyState message={t.quantLab.modelAdminEmpty} />
      )}
      {version && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.activeVersion}</h3>
          <p className="mt-1 text-xs text-zinc-400">
            strategy: {String(version.strategy_version ?? "—")} · factor:{" "}
            {String(version.factor_model_version ?? "—")}
          </p>
        </div>
      )}
      {factorsAdmin && factorCount != null && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.factorCatalog}</h3>
          <p className="text-xs text-zinc-500">
            {factorCount} factors · trade predictions:{" "}
            {String(factorsAdmin.trade_predictions_count ?? "—")} · outcomes:{" "}
            {String(factorsAdmin.trade_outcomes_count ?? "—")}
          </p>
        </div>
      )}
      {weights && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.dynamicWeights}</h3>
          <p className="text-xs text-zinc-500">
            {weights.sleeve} / {weights.regime} · dynamic={String(weights.dynamic_enabled)}
          </p>
        </div>
      )}
      {audit && audit.events.length > 0 && (
        <div className="surface-card p-4">
          <h3 className="text-sm font-semibold">{t.quantLab.auditLog}</h3>
          <ul className="mt-2 space-y-1 text-xs text-zinc-400">
            {audit.events.slice(0, 8).map((e, i) => (
              <li key={i}>
                {e.event_type} {e.symbol ? `· ${e.symbol}` : ""}
              </li>
            ))}
          </ul>
        </div>
      )}
      {audit && audit.events.length === 0 && (
        <p className="text-xs text-zinc-500">{t.quantLab.noAuditEvents}</p>
      )}
    </div>
  );
}
