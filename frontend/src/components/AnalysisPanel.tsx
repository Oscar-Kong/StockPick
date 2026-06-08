// Main symbol analysis panel — wide two-column layout with persistent metrics rail.
"use client";

import {
  explainStock,
  getAnalyzeBucketFit,
  getAnalyzeSymbol,
  getDataQuality,
  getV2PositionSizing,
  getV2Score,
  getResearchReport,
  listSavedReports,
  saveReportSnapshot,
  updateWatchlistNotes,
} from "@/lib/api";
import { getBucketMeta } from "@/lib/buckets";
import { useTranslation } from "@/lib/i18n";
import type { AnalyzeSymbolResponse, Bucket, PositionSizingV2, StockResearchReport, V2ScoreResponse } from "@/lib/types";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppTabBar, AppTabButton } from "./AppTabs";
import { AnalysisAlerts } from "./AnalysisAlerts";
import { AnalysisSidebar } from "./AnalysisSidebar";
import { BacktestPanel } from "./BacktestPanel";
import { DataQualityBadge } from "./DataQualityBadge";
import { PositionSizingBlock } from "./PositionSizingBlock";
import { PriceChart } from "./PriceChart";
import { ResearchReport } from "./ResearchReport";
import { Round2Panel } from "./Round2Panel";
import { ScoreBreakdown } from "./ScoreBreakdown";

const TABS = ["overview", "insights", "quant", "data", "chart", "backtest", "report"] as const;
type Tab = (typeof TABS)[number];

interface AnalysisPanelProps {
  symbol: string;
  bucket?: Bucket;
  initialNotes?: string;
  /** Fills workspace frame without extra outer card */
  embedded?: boolean;
}

function AnalysisLoading({ symbol, embedded }: { symbol: string; embedded?: boolean }) {
  const { t } = useTranslation();
  const [loadingBefore, loadingAfter] = t.analysis.loading.split("{symbol}");
  const shell = embedded
    ? "flex h-full min-h-0 flex-1 flex-col overflow-hidden"
    : "analysis-shell";
  return (
    <div className={shell}>
      <div className="analysis-toolbar shrink-0">
        <p className="text-xs text-zinc-400">
          {loadingBefore}
          <span className="font-semibold text-zinc-200">{symbol}</span>
          {loadingAfter}
        </p>
      </div>
      <div className="analysis-grid min-h-0 flex-1 overflow-hidden">
        <div className="analysis-primary space-y-3 p-4">
          <div className="h-4 w-2/3 animate-pulse rounded bg-zinc-800/80" />
          <div className="h-32 animate-pulse rounded-lg bg-zinc-800/60" />
        </div>
        <div className="analysis-rail hidden space-y-2 p-4 lg:block">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-zinc-800/50" />
          ))}
        </div>
      </div>
    </div>
  );
}

export function AnalysisPanel({
  symbol,
  bucket,
  initialNotes = "",
  embedded = false,
}: AnalysisPanelProps) {
  const { t } = useTranslation();
  const bucketMeta = getBucketMeta(t);

  const tabLabels = useMemo(
    (): Record<Tab, string> => ({
      overview: t.analysis.tabOverview,
      insights: t.analysis.tabInsights,
      quant: t.analysis.tabQuant,
      data: t.analysis.tabData,
      chart: t.analysis.tabChart,
      backtest: t.analysis.tabBacktest,
      report: t.analysis.tabReport,
    }),
    [t]
  );

  const riskLabel = useCallback(
    (level: string) => {
      if (level === "high") return t.risk.high;
      if (level === "low") return t.risk.low;
      return t.risk.medium;
    },
    [t]
  );

  const [tab, setTab] = useState<Tab>("overview");
  const [data, setData] = useState<AnalyzeSymbolResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState(initialNotes);
  const [savingNotes, setSavingNotes] = useState(false);
  const [narrative, setNarrative] = useState<string | null>(null);
  const [narrativeLoading, setNarrativeLoading] = useState(false);
  const [reconcileFields, setReconcileFields] = useState<
    { field: string; value: number | null; confidence: string }[]
  >([]);
  const [dataTabLoading, setDataTabLoading] = useState(false);
  const [bucketFit, setBucketFit] = useState<AnalyzeSymbolResponse["bucket_fit"] | null>(null);
  const [bucketFitLoading, setBucketFitLoading] = useState(false);
  const [report, setReport] = useState<StockResearchReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [savingReport, setSavingReport] = useState(false);
  const [reportMsg, setReportMsg] = useState<string | null>(null);
  const [positionSizing, setPositionSizing] = useState<PositionSizingV2 | null>(null);
  const [sizingLoading, setSizingLoading] = useState(false);
  const [sizingError, setSizingError] = useState<string | null>(null);
  const [v2Score, setV2Score] = useState<V2ScoreResponse | null>(null);
  const [v2Loading, setV2Loading] = useState(false);
  const loadGenRef = useRef(0);

  useEffect(() => {
    if (!symbol) return;

    const gen = ++loadGenRef.current;
    const ac = new AbortController();

    setData(null);
    setError(null);
    setLoading(true);
    setNotes(initialNotes);
    setTab("overview");
    setNarrative(null);
    setReconcileFields([]);
    setBucketFit(null);
    setBucketFitLoading(false);
    setReport(null);
    setReportError(null);
    setReportMsg(null);
    setPositionSizing(null);
    setSizingError(null);

    void (async () => {
      try {
        const res = await getAnalyzeSymbol(symbol, bucket, { signal: ac.signal });
        if (gen !== loadGenRef.current) return;
        setData(res);
      } catch (err) {
        if (ac.signal.aborted || gen !== loadGenRef.current) return;
        setError(err instanceof Error ? err.message : t.analysis.failed);
        setData(null);
      } finally {
        if (gen === loadGenRef.current) setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [symbol, bucket, initialNotes, t]);

  useEffect(() => {
    if (!data || data.symbol !== symbol) return;
    const scores = bucketFit?.scores ?? data.bucket_fit?.scores ?? {};
    if (Object.keys(scores).length > 0) return;

    const ac = new AbortController();
    setBucketFitLoading(true);
    void getAnalyzeBucketFit(symbol, { signal: ac.signal })
      .then((fit) => {
        if (!ac.signal.aborted) setBucketFit(fit);
      })
      .catch(() => {
        if (!ac.signal.aborted) setBucketFit(data.bucket_fit);
      })
      .finally(() => {
        if (!ac.signal.aborted) setBucketFitLoading(false);
      });

    return () => ac.abort();
  }, [data, symbol, bucketFit?.scores]);

  useEffect(() => {
    if (!data || data.symbol !== symbol) return;
    const ac = new AbortController();
    const b = (bucket ?? data.assigned_bucket) as Bucket;
    setV2Loading(true);
    setSizingLoading(true);
    setSizingError(null);
    void getV2Score(symbol, b, { signal: ac.signal })
      .then((s) => {
        if (ac.signal.aborted) return;
        setV2Score(s);
        if (s.position_sizing) {
          setPositionSizing(s.position_sizing);
          setSizingLoading(false);
        } else {
          return getV2PositionSizing(symbol, b, { signal: ac.signal })
            .then((sz) => {
              if (!ac.signal.aborted) setPositionSizing(sz);
            })
            .catch((err) => {
              if (ac.signal.aborted) return;
              const msg = err instanceof Error ? err.message : t.analysis.sizingUnavailable;
              if (!msg.includes("503")) setSizingError(msg);
              setPositionSizing(null);
            })
            .finally(() => {
              if (!ac.signal.aborted) setSizingLoading(false);
            });
        }
      })
      .catch(() => {
        if (!ac.signal.aborted) setV2Score(null);
        setSizingLoading(false);
      })
      .finally(() => {
        if (!ac.signal.aborted) setV2Loading(false);
      });
    return () => ac.abort();
  }, [data, symbol, bucket, t]);

  useEffect(() => {
    if (tab !== "data" || !data || data.symbol !== symbol) return;
    if (reconcileFields.length > 0) return;

    const ac = new AbortController();
    setDataTabLoading(true);
    void getDataQuality(symbol)
      .then((q) => {
        if (ac.signal.aborted) return;
        const fields =
          (q.reconcile?.fields as { field: string; value: number | null; confidence: string }[]) ??
          [];
        setReconcileFields(fields);
      })
      .catch(() => {
        if (!ac.signal.aborted) setReconcileFields([]);
      })
      .finally(() => {
        if (!ac.signal.aborted) setDataTabLoading(false);
      });

    return () => ac.abort();
  }, [tab, symbol, data, reconcileFields.length]);

  useEffect(() => {
    if (tab !== "report" || !symbol) return;
    if (report) return;

    const ac = new AbortController();
    void listSavedReports(symbol)
      .then((reports) => {
        if (ac.signal.aborted) return;
        if (reports.length > 0 && reports[0].report && !("error" in reports[0].report)) {
          setReport(reports[0].report as StockResearchReport);
        }
      })
      .catch(() => {});

    return () => ac.abort();
  }, [tab, symbol, report]);

  const refresh = useCallback(async () => {
    if (!symbol) return;
    const gen = ++loadGenRef.current;
    const ac = new AbortController();
    setData(null);
    setLoading(true);
    setError(null);
    setBucketFit(null);
    try {
      const res = await getAnalyzeSymbol(symbol, bucket, {
        signal: ac.signal,
        refresh: true,
      });
      if (gen !== loadGenRef.current) return;
      setData(res);
    } catch (err) {
      if (ac.signal.aborted || gen !== loadGenRef.current) return;
      setError(err instanceof Error ? err.message : t.analysis.failed);
    } finally {
      if (gen === loadGenRef.current) setLoading(false);
    }
  }, [symbol, bucket, t]);

  const saveNotes = async () => {
    setSavingNotes(true);
    try {
      await updateWatchlistNotes(symbol, notes);
    } finally {
      setSavingNotes(false);
    }
  };

  const generateNarrative = async () => {
    if (!data) return;
    setNarrativeLoading(true);
    try {
      const res = await explainStock(symbol, data.assigned_bucket);
      setNarrative(res.explanation);
    } catch {
      setNarrative(t.analysis.narrativeFailed);
    } finally {
      setNarrativeLoading(false);
    }
  };

  const generateReport = async () => {
    setReportLoading(true);
    setReportError(null);
    setReportMsg(null);
    try {
      const res = await getResearchReport(symbol, bucket);
      setReport(res);
    } catch (err) {
      setReport(null);
      setReportError(err instanceof Error ? err.message : t.analysis.reportFailed);
    } finally {
      setReportLoading(false);
    }
  };

  const saveReport = async () => {
    if (!report || report.error || !data) return;
    setSavingReport(true);
    setReportMsg(null);
    try {
      await saveReportSnapshot({
        symbol,
        bucket: data.assigned_bucket,
        report,
      });
      setReportMsg(t.analysis.reportSaved);
    } catch (err) {
      setReportMsg(err instanceof Error ? err.message : t.analysis.saveReportFailed);
    } finally {
      setSavingReport(false);
    }
  };

  if (!symbol) {
    return (
      <p className="p-6 text-sm text-zinc-500">{t.analysis.selectSymbol}</p>
    );
  }

  const ready = data && data.symbol === symbol && !loading;

  if (!ready) {
    if (error) {
      return (
        <div
          className={
            embedded
              ? "flex flex-1 items-start p-6"
              : "analysis-shell p-6"
          }
        >
          <p className="text-sm text-red-400">{error}</p>
          <button type="button" onClick={() => void refresh()} className="btn-ghost mt-3 px-3 py-1.5 text-xs">
            {t.common.retry}
          </button>
        </div>
      );
    }
    return <AnalysisLoading symbol={symbol} embedded={embedded} />;
  }

  const activeBucketFit = bucketFit ?? data.bucket_fit;
  const bucketScores = activeBucketFit?.scores ?? {};
  const shellClass = embedded
    ? "flex h-full min-h-0 flex-1 flex-col overflow-hidden"
    : "analysis-shell flex flex-col min-h-[70vh]";

  const reconcileRows =
    reconcileFields.length > 0
      ? reconcileFields
      : Object.entries(data.reconcile.canonical ?? {}).map(([field, v]) => ({
          field,
          value: typeof v === "number" ? v : null,
          confidence: "—",
        }));

  return (
    <div className={shellClass}>
      <div className="analysis-toolbar shrink-0">
        <div className="analysis-toolbar-left">
          <h2 className="text-zinc-50">{data.symbol}</h2>
          <div className="flex flex-wrap items-center gap-1 text-xs">
            <span className="chip px-1.5 py-0.5 tabular-nums">${data.price.toFixed(2)}</span>
            <span className="chip px-1.5 py-0.5 capitalize">
              {bucketMeta[data.assigned_bucket as Bucket]?.label ?? data.assigned_bucket}
            </span>
            <span className="chip px-1.5 py-0.5">
              {t.analysis.scoreChip} {data.score.toFixed(1)}
            </span>
            <span
              className={clsx(
                "chip px-1.5 py-0.5 capitalize",
                data.risk_level === "high" && "text-red-300",
                data.risk_level === "medium" && "text-amber-300",
                data.risk_level === "low" && "text-[#7dff8e]"
              )}
            >
              {riskLabel(data.risk_level)}
            </span>
          </div>
        </div>
        <div className="analysis-toolbar-right">
          <AppTabBar aria-label={t.analysis.viewsAria}>
            {TABS.map((tabKey) => (
              <AppTabButton key={tabKey} active={tab === tabKey} onClick={() => setTab(tabKey)}>
                {tabLabels[tabKey]}
              </AppTabButton>
            ))}
          </AppTabBar>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="btn-ghost shrink-0 px-2 py-1 text-xs"
          >
            {loading ? "…" : t.common.refresh}
          </button>
        </div>
      </div>

      <div className="analysis-meta shrink-0">
        <DataQualityBadge score={data.data_quality_score} flags={[]} />
        <AnalysisAlerts alerts={data.alerts} />
      </div>

      <div className="analysis-grid min-h-0 flex-1 overflow-hidden">
        <div className="analysis-primary p-3 lg:p-4">
          {tab === "overview" && (
            <div className="grid gap-4 xl:grid-cols-2">
              <div className="analysis-block xl:col-span-2">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  {t.analysis.summary}
                </h3>
                <p className="text-sm leading-relaxed text-zinc-300">{data.summary}</p>
              </div>
              <div className="analysis-block">
                <label className="text-xs font-medium text-zinc-500">{t.analysis.yourNotes}</label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={5}
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 p-2 text-sm text-zinc-100"
                />
                <button
                  type="button"
                  onClick={saveNotes}
                  disabled={savingNotes}
                  className="btn-ghost mt-2 px-2 py-1 text-xs"
                >
                  {savingNotes ? t.common.saving : t.analysis.saveNotes}
                </button>
              </div>
              <div className="analysis-block flex flex-col">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                  {t.analysis.aiNarrative}
                </h3>
                <button
                  type="button"
                  onClick={generateNarrative}
                  disabled={narrativeLoading}
                  className="btn-primary mt-2 w-fit px-3 py-1.5 text-sm"
                >
                  {narrativeLoading ? t.common.generating : t.analysis.generateNarrative}
                </button>
                {narrative ? (
                  <p className="mt-3 flex-1 overflow-y-auto whitespace-pre-wrap text-sm text-zinc-400">
                    {narrative}
                  </p>
                ) : (
                  <p className="mt-3 text-xs text-zinc-600">{t.analysis.narrativeHint}</p>
                )}
              </div>
            </div>
          )}

          {tab === "insights" && (
            <div className="space-y-4">
              {v2Loading && (
                <p className="text-xs text-zinc-500">{t.analysis.loadingQuantV2}</p>
              )}
              {v2Score ? (
                <Round2Panel score={v2Score} />
              ) : (
                !v2Loading && (
                  <p className="text-sm text-zinc-500">{t.analysis.insightsUnavailable}</p>
                )
              )}
              {!v2Score?.position_sizing && (
                <div className="analysis-block">
                  <h3 className="label-caps mb-2">{t.analysis.positionSizing}</h3>
                  <PositionSizingBlock
                    sizing={positionSizing}
                    loading={sizingLoading}
                    error={sizingError}
                  />
                </div>
              )}
            </div>
          )}

          {tab === "quant" && (
            <div className="space-y-4">
              <ScoreBreakdown signals={data.signals} className="analysis-chart-box h-80 w-full p-3" />
              <div className="analysis-block lg:hidden">
                <h4 className="mb-2 text-sm font-semibold text-zinc-200">{t.analysis.bucketFit}</h4>
                {bucketFitLoading ? (
                  <p className="text-xs text-zinc-500">{t.common.loading}</p>
                ) : (
                  <div className="grid grid-cols-3 gap-2">
                    {(["penny", "medium", "compounder"] as Bucket[]).map((b) => {
                      const s = bucketScores[b];
                      const active = b === data.assigned_bucket;
                      return (
                        <div
                          key={b}
                          className={clsx(
                            "rounded-lg border p-2 text-center",
                            active
                              ? "border-[#00c805]/40 bg-[#00c805]/10"
                              : "border-zinc-800"
                          )}
                        >
                          <p className="text-xs capitalize text-zinc-500">{bucketMeta[b].label}</p>
                          <p className="text-lg font-semibold">{s?.score?.toFixed(1) ?? "—"}</p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === "data" && (
            <div className="analysis-block">
              {dataTabLoading ? (
                <p className="text-xs text-zinc-500">{t.analysis.loadingReconcile}</p>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-zinc-500">
                      <th className="py-1 pr-4">{t.common.field}</th>
                      <th className="py-1 pr-4">{t.common.value}</th>
                      <th className="py-1">{t.common.confidence}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reconcileRows.map((f) => (
                      <tr key={f.field} className="border-t border-zinc-800">
                        <td className="py-2 pr-4 text-zinc-300">{f.field}</td>
                        <td className="py-2 pr-4 tabular-nums text-zinc-200">
                          {typeof f.value === "number" ? f.value.toFixed(2) : "—"}
                        </td>
                        <td className="py-2 capitalize text-zinc-500">{f.confidence}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === "chart" && (
            <div className="analysis-block p-2">
              <PriceChart ohlc={data.ohlc} />
            </div>
          )}

          {tab === "backtest" && <BacktestPanel symbol={data.symbol} bucket={data.assigned_bucket} />}

          {tab === "report" && (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={generateReport}
                  disabled={reportLoading}
                  className="btn-primary px-3 py-1.5 text-sm"
                >
                  {reportLoading ? t.common.generating : t.analysis.generateReport}
                </button>
                <button
                  type="button"
                  onClick={saveReport}
                  disabled={savingReport || !report || !!report.error}
                  className="btn-ghost px-3 py-1.5 text-sm"
                >
                  {savingReport ? t.common.saving : t.analysis.saveReport}
                </button>
              </div>
              {reportMsg && <p className="text-xs text-zinc-500">{reportMsg}</p>}
              <ResearchReport report={report} loading={reportLoading} error={reportError} />
            </div>
          )}
        </div>

        <aside className="analysis-rail hidden lg:block">
          <AnalysisSidebar
            data={data}
            bucketFit={activeBucketFit}
            bucketFitLoading={bucketFitLoading}
          />
        </aside>
      </div>
    </div>
  );
}
