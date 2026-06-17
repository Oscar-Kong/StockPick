// Main symbol analysis panel — wide two-column layout with persistent metrics rail.
"use client";

import {
  getAnalyzeBucketFit,
  getAnalyzeSymbol,
  getSymbolDiagnostics,
  getV2PositionSizing,
  getV2Score,
  getV2UnifiedRisk,
  getResearchReport,
  listSavedReports,
  saveReportSnapshot,
  updateWatchlistNotes,
} from "@/lib/api";
import { getBucketMeta } from "@/lib/buckets";
import { useTranslation, useTRef } from "@/lib/i18n";
import type { AnalyzeSymbolResponse, Bucket, PositionSizingV2, StockResearchReport, SymbolDiagnosticsResponse, UnifiedRiskV2, V2ScoreResponse } from "@/lib/types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnalysisAlerts } from "./AnalysisAlerts";
import { AnalysisHeaderStats } from "./AnalysisHeaderStats";
import { AnalysisSidebar } from "./AnalysisSidebar";
import { AnalysisSymbolNav } from "./AnalysisSymbolNav";
import { AnalysisTabNav, type AnalysisTabConfig, type AnalysisTabId } from "./AnalysisTabNav";
import { BacktestPanel } from "./BacktestPanel";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { PositionSizingBlock } from "./PositionSizingBlock";
import { PriceChart } from "./PriceChart";
import { ResearchReport } from "./ResearchReport";
import { Round2Panel } from "./Round2Panel";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { UnifiedRiskPanel } from "./UnifiedRiskPanel";
import { V2FallbackBanner } from "./V2FallbackBanner";
import { FactorAttributionTable } from "./quant/FactorAttributionTable";
import { NotFinancialAdviceFooter } from "./ui/NotFinancialAdviceFooter";
import { ResearchWarning } from "./ui/ResearchWarning";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import { ValuationBlock } from "./ValuationBlock";
import {
  parseV2FetchError,
  resolveAnalysisDisplay,
  scoreSourcesDiffer,
  type V2UnavailableReason,
} from "@/lib/v2Score";

interface AnalysisPanelProps {
  symbol: string;
  bucket?: Bucket;
  initialNotes?: string;
  /** Fills workspace frame without extra outer card */
  embedded?: boolean;
  prevSymbol?: string | null;
  nextSymbol?: string | null;
  onNavigateSymbol?: (symbol: string) => void;
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
  prevSymbol = null,
  nextSymbol = null,
  onNavigateSymbol,
}: AnalysisPanelProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const bucketMeta = getBucketMeta(t);

  const tabConfigs = useMemo(
    (): AnalysisTabConfig[] => [
      {
        id: "overview",
        label: t.analysis.tabOverview,
        shortLabel: t.analysis.tabOverviewShort,
        hint: t.analysis.tabOverviewHint,
        group: "core",
      },
      {
        id: "score",
        label: t.analysis.tabScoreBreakdown,
        shortLabel: t.analysis.tabScoreShort,
        hint: t.analysis.tabScoreHint,
        group: "core",
      },
      {
        id: "risk",
        label: t.analysis.tabRisk,
        shortLabel: t.analysis.tabRiskShort,
        hint: t.analysis.tabRiskHint,
        group: "core",
      },
      {
        id: "diagnostics",
        label: t.analysis.tabDiagnostics,
        shortLabel: t.analysis.tabDiagnosticsShort,
        hint: t.analysis.tabDiagnosticsHint,
        group: "research",
      },
      {
        id: "valuation",
        label: t.analysis.tabValuation,
        shortLabel: t.analysis.tabValuationShort,
        hint: t.analysis.tabValuationHint,
        group: "research",
      },
      {
        id: "backtest",
        label: t.analysis.tabBacktest,
        shortLabel: t.analysis.tabBacktestShort,
        hint: t.analysis.tabBacktestHint,
        group: "research",
      },
      {
        id: "similar",
        label: t.analysis.tabSimilar,
        shortLabel: t.analysis.tabSimilarShort,
        hint: t.analysis.tabSimilarHint,
        group: "research",
      },
      {
        id: "report",
        label: t.analysis.tabReport,
        shortLabel: t.analysis.tabReportShort,
        hint: t.analysis.tabReportHint,
        group: "workspace",
      },
      {
        id: "notes",
        label: t.analysis.tabNotes,
        shortLabel: t.analysis.tabNotesShort,
        hint: t.analysis.tabNotesHint,
        group: "workspace",
      },
    ],
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

  const [tab, setTab] = useState<AnalysisTabId>("overview");
  const [insightsOpen, setInsightsOpen] = useState(false);
  const [data, setData] = useState<AnalyzeSymbolResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState(initialNotes);
  const [savingNotes, setSavingNotes] = useState(false);
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
  const [v2UnavailableReason, setV2UnavailableReason] = useState<V2UnavailableReason | null>(null);
  const [diagnostics, setDiagnostics] = useState<SymbolDiagnosticsResponse | null>(null);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);
  const [unifiedRisk, setUnifiedRisk] = useState<UnifiedRiskV2 | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);
  const diagnosticsOkRef = useRef<string | null>(null);
  const riskOkRef = useRef<string | null>(null);
  const [insightsRetryTick, setInsightsRetryTick] = useState(0);
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
    setInsightsOpen(false);
    setBucketFit(null);
    setBucketFitLoading(false);
    setReport(null);
    setReportError(null);
    setReportMsg(null);
    setPositionSizing(null);
    setSizingError(null);
    setV2Score(null);
    setV2UnavailableReason(null);
    setDiagnostics(null);
    setDiagnosticsError(null);
    setUnifiedRisk(null);
    setRiskError(null);
    diagnosticsOkRef.current = null;
    riskOkRef.current = null;
    setInsightsRetryTick(0);

    void (async () => {
      try {
        const res = await getAnalyzeSymbol(symbol, bucket, { signal: ac.signal });
        if (gen !== loadGenRef.current) return;
        setData(res);
      } catch (err) {
        if (ac.signal.aborted || gen !== loadGenRef.current) return;
        setError(err instanceof Error ? err.message : tRef.current.analysis.failed);
        setData(null);
      } finally {
        if (gen === loadGenRef.current) setLoading(false);
      }
    })();

    return () => ac.abort();
  }, [symbol, bucket, initialNotes, tRef]);

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
    setV2UnavailableReason(null);
    void getV2Score(symbol, b, { signal: ac.signal })
      .then((s) => {
        if (ac.signal.aborted) return;
        setV2Score(s);
        setV2UnavailableReason(null);
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
              const msg = err instanceof Error ? err.message : tRef.current.analysis.sizingUnavailable;
              if (!msg.includes("503")) setSizingError(msg);
              setPositionSizing(null);
            })
            .finally(() => {
              if (!ac.signal.aborted) setSizingLoading(false);
            });
        }
      })
      .catch((err) => {
        if (!ac.signal.aborted) {
          setV2Score(null);
          setV2UnavailableReason(parseV2FetchError(err));
        }
        setSizingLoading(false);
      })
      .finally(() => {
        if (!ac.signal.aborted) setV2Loading(false);
      });
    return () => ac.abort();
  }, [data, symbol, bucket, tRef]);

  const retryDiagnostics = useCallback(() => {
    diagnosticsOkRef.current = null;
    setInsightsRetryTick((n) => n + 1);
  }, []);

  const retryUnifiedRisk = useCallback(() => {
    riskOkRef.current = null;
    setInsightsRetryTick((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!data || data.symbol !== symbol) return;
    const b = (bucket ?? data.assigned_bucket) as Bucket;
    const cacheKey = `${symbol}:${b}`;
    const ac = new AbortController();

    if (tab === "diagnostics" && diagnosticsOkRef.current !== cacheKey) {
      setDiagnosticsLoading(true);
      setDiagnosticsError(null);
      void getSymbolDiagnostics(symbol, 252, { signal: ac.signal })
        .then((diag) => {
          if (ac.signal.aborted) return;
          setDiagnostics(diag);
          diagnosticsOkRef.current = cacheKey;
        })
        .catch((err) => {
          if (ac.signal.aborted) return;
          setDiagnosticsError(err instanceof Error ? err.message : tRef.current.analysis.failed);
        })
        .finally(() => {
          if (!ac.signal.aborted) setDiagnosticsLoading(false);
        });
    }

    if (tab === "risk" && riskOkRef.current !== cacheKey) {
      setRiskLoading(true);
      setRiskError(null);
      void getV2UnifiedRisk(symbol, b, { signal: ac.signal })
        .then((risk) => {
          if (ac.signal.aborted) return;
          setUnifiedRisk(risk);
          riskOkRef.current = cacheKey;
        })
        .catch((err) => {
          if (ac.signal.aborted) return;
          const msg = err instanceof Error ? err.message : tRef.current.analysis.failed;
          setRiskError(
            msg.includes("503") || msg.toLowerCase().includes("score_engine")
              ? tRef.current.riskPanel.v2Disabled
              : msg
          );
        })
        .finally(() => {
          if (!ac.signal.aborted) setRiskLoading(false);
        });
    }

    return () => ac.abort();
  }, [tab, data, symbol, bucket, insightsRetryTick, tRef]);

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
      setError(err instanceof Error ? err.message : tRef.current.analysis.failed);
    } finally {
      if (gen === loadGenRef.current) setLoading(false);
    }
  }, [symbol, bucket, tRef]);

  const saveNotes = async () => {
    setSavingNotes(true);
    try {
      await updateWatchlistNotes(symbol, notes);
    } finally {
      setSavingNotes(false);
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
  const display = resolveAnalysisDisplay(data, v2Score);
  const showLegacyDiff = display.hasV2 && scoreSourcesDiffer(display);
  const shellClass = embedded
    ? "flex h-full min-h-0 flex-1 flex-col overflow-hidden"
    : "analysis-shell flex flex-col min-h-[70vh]";

  return (
    <div className={shellClass}>
      <div className="analysis-toolbar shrink-0">
        <div className="analysis-toolbar__head">
          <div className="analysis-toolbar__identity">
            <AnalysisSymbolNav
              symbol={data.symbol}
              prevSymbol={prevSymbol}
              nextSymbol={nextSymbol}
              onNavigate={onNavigateSymbol}
            />
            {!onNavigateSymbol && (
              <h2 className="analysis-toolbar__symbol-title">{data.symbol}</h2>
            )}
          </div>
          <div className="analysis-toolbar__actions">
            <button
              type="button"
              onClick={() => setInsightsOpen(true)}
              className="analysis-insights-toggle lg:hidden"
              hidden={tab === "overview"}
            >
              {t.analysis.openInsights}
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading}
              className="btn-ghost shrink-0 px-3 py-1.5 text-sm"
            >
              {loading ? "…" : t.common.refresh}
            </button>
          </div>
        </div>

        <AnalysisHeaderStats
          price={data.price}
          changePct1d={(() => {
            const n = Number(data.metrics?.change_pct_1d);
            return Number.isFinite(n) ? n : null;
          })()}
          recommendation={(data.metrics?.recommendation as string) ?? null}
          bucketLabel={bucketMeta[data.assigned_bucket as Bucket]?.label ?? data.assigned_bucket}
          score={display.score}
          scoreSource={display.scoreSource}
          riskLevel={String(display.riskLevel)}
          riskLabel={riskLabel(String(display.riskLevel))}
          dataQualityScore={data.data_quality_score}
          priceHistoryLastDate={data.price_history_last_date}
          priceHistoryIsStale={data.price_history_is_stale}
          legacyScore={display.legacyScore}
          showLegacyDiff={showLegacyDiff}
        />

        <AnalysisTabNav
          tabs={tabConfigs}
          active={tab}
          onChange={setTab}
          ariaLabel={t.analysis.viewsAria}
        />
      </div>

      {data.alerts.length > 0 && (
        <div className="analysis-meta shrink-0">
          <AnalysisAlerts alerts={data.alerts} />
        </div>
      )}

      <div className="analysis-grid min-h-0 flex-1 overflow-hidden">
        <div className="analysis-primary p-3 lg:p-4">
          {tab === "overview" && (
            <div className="space-y-4">
              {v2Loading && <p className="text-xs text-zinc-500">{t.analysis.loadingQuantV2}</p>}
              {!v2Loading && !v2Score && v2UnavailableReason && (
                <V2FallbackBanner reason={v2UnavailableReason} />
              )}
              <div className="analysis-overview-grid">
                <div className="analysis-overview-chart">
                  <PriceChart
                    ohlc={data.ohlc}
                    priceHistoryLastDate={data.price_history_last_date}
                    priceHistoryIsStale={data.price_history_is_stale}
                    priceHistoryRefreshedAt={data.price_history_refreshed_at}
                  />
                </div>
                <div className="analysis-overview-side">
                  {v2Score ? (
                    <Round2Panel score={v2Score} />
                  ) : (
                    !v2Loading && (
                      <div className="analysis-section">
                        <h3 className="analysis-section__title">{t.analysis.summary}</h3>
                        <p className="text-sm leading-relaxed text-secondary">{display.summary}</p>
                      </div>
                    )
                  )}
                  <div className="analysis-section">
                    <h3 className="analysis-section__title">{t.analysis.positionSizing}</h3>
                    <PositionSizingBlock
                      sizing={positionSizing ?? v2Score?.position_sizing ?? null}
                      loading={sizingLoading}
                      error={sizingError}
                    />
                  </div>
                  {data.valuation_warnings?.length > 0 && (
                    <div className="analysis-section">
                      <h3 className="analysis-section__title">{t.analysis.tabValuation}</h3>
                      <ul className="space-y-1 text-sm text-amber-200/90">
                        {data.valuation_warnings.map((w) => (
                          <li key={w}>{w}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
              {v2Score?.factors && v2Score.factors.length > 0 && (
                <div className="analysis-section mt-3">
                  <FactorAttributionTable factors={v2Score.factors} />
                </div>
              )}
            </div>
          )}

          {tab === "score" && (
            <div className="space-y-4">
              {v2Loading && <p className="text-xs text-zinc-500">{t.analysis.loadingQuantV2}</p>}
              {v2Score ? (
                <>
                  <FactorAttributionTable factors={v2Score.factors} />
                  {v2Score.parity_delta != null && (
                    <p className="text-xs text-zinc-500">
                      {t.scanDrawer.parityDelta}: {v2Score.parity_delta.toFixed(2)}
                    </p>
                  )}
                  <ScoreBreakdown signals={data.signals} className="analysis-chart-box h-64 w-full p-3" />
                </>
              ) : (
                <ScoreBreakdown signals={data.signals} className="analysis-chart-box h-80 w-full p-3" />
              )}
            </div>
          )}

          {tab === "risk" && (
            <UnifiedRiskPanel
              data={unifiedRisk}
              loading={riskLoading}
              error={riskError}
              onRetry={riskError ? retryUnifiedRisk : undefined}
            />
          )}

          {tab === "diagnostics" && (
            <DiagnosticsPanel
              data={diagnostics}
              loading={diagnosticsLoading}
              error={diagnosticsError}
              onRetry={diagnosticsError ? retryDiagnostics : undefined}
            />
          )}

          {tab === "valuation" && (
            <div className="space-y-3">
              {v2Score?.valuation ? (
                <ValuationBlock data={v2Score.valuation} />
              ) : (
                <p className="text-sm text-zinc-500">{t.analysis.valuationUnavailable}</p>
              )}
            </div>
          )}

          {tab === "backtest" && <BacktestPanel symbol={data.symbol} bucket={data.assigned_bucket} />}

          {tab === "similar" && (
            <div className="space-y-3">
              <ResearchWarning />
              {v2Score?.similar_signal ? (
                <SimilarSignalBlock data={v2Score.similar_signal} />
              ) : (
                <p className="text-sm text-zinc-500">{t.quant.similarInsufficient}</p>
              )}
            </div>
          )}

          {tab === "report" && (
            <div className="space-y-3">
              <p className="text-xs text-zinc-400">{t.analysis.llmDoesNotOverride}</p>
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
              <NotFinancialAdviceFooter llmNote />
            </div>
          )}

          {tab === "notes" && (
            <div className="analysis-block">
              <label className="text-xs font-medium text-zinc-500">{t.analysis.yourNotes}</label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={8}
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
          )}
        </div>

        {tab !== "overview" && (
          <aside className="analysis-rail hidden lg:block">
            <AnalysisSidebar
              data={data}
              bucketFit={activeBucketFit}
              bucketFitLoading={bucketFitLoading}
              display={display}
              v2Score={v2Score}
              compact
            />
          </aside>
        )}
      </div>

      {insightsOpen && (
        <div className="analysis-insights-backdrop lg:hidden" role="presentation">
          <button
            type="button"
            className="analysis-insights-backdrop-hit"
            aria-label={t.common.close}
            onClick={() => setInsightsOpen(false)}
          />
          <div className="analysis-insights-sheet" role="dialog" aria-modal="true" aria-label={t.analysis.insightsPanelTitle}>
            <div className="analysis-insights-sheet-header">
              <h3 className="text-sm font-semibold text-zinc-100">{t.analysis.insightsPanelTitle}</h3>
              <button
                type="button"
                className="btn-ghost px-2 py-1 text-xs"
                onClick={() => setInsightsOpen(false)}
              >
                {t.common.close}
              </button>
            </div>
            <div className="analysis-insights-sheet-body">
              <AnalysisSidebar
                data={data}
                bucketFit={activeBucketFit}
                bucketFitLoading={bucketFitLoading}
                display={display}
                v2Score={v2Score}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
