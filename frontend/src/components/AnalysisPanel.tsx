// Main symbol analysis panel — snapshot-first core load with decision Overview.
"use client";

import dynamic from "next/dynamic";
import {
  getAnalyzeBucketFit,
  getAnalyzeCore,
  getAnalyzeSnapshot,
  getSymbolDiagnostics,
  getV2UnifiedRisk,
  getResearchReport,
  listSavedReports,
  saveReportSnapshot,
  updateWatchlistNotes,
} from "@/lib/api";
import {
  analysisCacheKey,
  clearAnalysisCache,
  getAnalysisCache,
  setAnalysisCache,
} from "@/lib/analysisClientCache";
import { getBucketMeta } from "@/lib/buckets";
import { useTranslation, useTRef } from "@/lib/i18n";
import type {
  AnalyzeDelta,
  AnalyzeFreshness,
  AnalyzeSymbolResponse,
  AnalyzeTradePlan,
  Bucket,
  PositionSizingV2,
  StockResearchReport,
  SymbolDiagnosticsResponse,
  UnifiedRiskV2,
  V2ScoreResponse,
} from "@/lib/types";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AnalysisAlerts } from "./AnalysisAlerts";
import { AnalysisHeaderStats } from "./AnalysisHeaderStats";
import { AnalysisSidebar } from "./AnalysisSidebar";
import { AnalysisSymbolNav } from "./AnalysisSymbolNav";
import {
  AnalysisTabNav,
  analysisPanelId,
  normalizeAnalysisTab,
  type AnalysisTabConfig,
  type AnalysisTabId,
} from "./AnalysisTabNav";
import { DecisionOverviewDetails, DecisionOverviewLead } from "./DecisionOverview";
import { PositionSizingBlock } from "./PositionSizingBlock";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { V2FallbackBanner } from "./V2FallbackBanner";
import { FactorAttributionTable } from "./quant/FactorAttributionTable";
import { NotFinancialAdviceFooter } from "./ui/NotFinancialAdviceFooter";
import { ResearchWarning } from "./ui/ResearchWarning";
import { ErrorState } from "./ui/ErrorState";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import { ValuationBlock } from "./ValuationBlock";
import {
  parseV2FetchError,
  resolveAnalysisDisplay,
  scoreSourcesDiffer,
  type V2UnavailableReason,
} from "@/lib/v2Score";
import { explainAnalysisLoadError, isAbortError } from "@/lib/workspaceLoadError";

const PriceChart = dynamic(
  () => import("./PriceChart").then((m) => m.PriceChart),
  { loading: () => <div className="analysis-loading__chart" /> }
);
const BacktestPanel = dynamic(
  () => import("./BacktestPanel").then((m) => m.BacktestPanel),
  { loading: () => <p className="text-xs text-zinc-500">…</p> }
);
const DiagnosticsPanel = dynamic(
  () => import("./DiagnosticsPanel").then((m) => m.DiagnosticsPanel),
  { loading: () => <p className="text-xs text-zinc-500">…</p> }
);
const UnifiedRiskPanel = dynamic(
  () => import("./UnifiedRiskPanel").then((m) => m.UnifiedRiskPanel),
  { loading: () => <p className="text-xs text-zinc-500">…</p> }
);
const ResearchReport = dynamic(
  () => import("./ResearchReport").then((m) => m.ResearchReport),
  { loading: () => <p className="text-xs text-zinc-500">…</p> }
);

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
          <div className="analysis-loading">
            <div className="analysis-loading__bar analysis-loading__bar--wide" />
            <div className="analysis-loading__hero">
              <div className="analysis-loading__bar analysis-loading__bar--price" />
              <div className="analysis-loading__bar analysis-loading__bar--pill" />
            </div>
            <div className="analysis-loading__grid">
              {[0, 1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="analysis-loading__tile" />
              ))}
            </div>
            <div className="analysis-loading__chart" />
          </div>
        </div>
        <div className="analysis-rail hidden space-y-2 p-4 lg:block">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="analysis-loading__tile analysis-loading__tile--rail" />
          ))}
        </div>
      </div>
    </div>
  );
}

function applyCorePayload(
  setData: (d: AnalyzeSymbolResponse) => void,
  setV2Score: (v: V2ScoreResponse | null) => void,
  setPositionSizing: (p: PositionSizingV2 | null) => void,
  setTradePlan: (p: AnalyzeTradePlan | null) => void,
  setDelta: (d: AnalyzeDelta | null) => void,
  setFreshness: (f: AnalyzeFreshness | null) => void,
  setV2UnavailableReason: (r: V2UnavailableReason | null) => void,
  payload: {
    base?: AnalyzeSymbolResponse | null;
    v2?: V2ScoreResponse | null;
    trade_plan?: AnalyzeTradePlan | null;
    delta?: AnalyzeDelta | null;
    freshness?: AnalyzeFreshness | null;
  }
) {
  if (payload.base) setData(payload.base);
  if (payload.v2) {
    setV2Score(payload.v2);
    setV2UnavailableReason(null);
    if (payload.v2.position_sizing) setPositionSizing(payload.v2.position_sizing);
  }
  if (payload.trade_plan !== undefined) setTradePlan(payload.trade_plan ?? null);
  if (payload.delta !== undefined) setDelta(payload.delta ?? null);
  if (payload.freshness) setFreshness(payload.freshness);
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
      },
      {
        id: "drivers",
        label: t.analysis.tabDrivers,
        shortLabel: t.analysis.tabDriversShort,
        hint: t.analysis.tabDriversHint,
      },
      {
        id: "risk",
        label: t.analysis.tabRisk,
        shortLabel: t.analysis.tabRiskShort,
        hint: t.analysis.tabRiskHint,
      },
      {
        id: "evidence",
        label: t.analysis.tabEvidence,
        shortLabel: t.analysis.tabEvidenceShort,
        hint: t.analysis.tabEvidenceHint,
      },
      {
        id: "research",
        label: t.analysis.tabResearch,
        shortLabel: t.analysis.tabResearchShort,
        hint: t.analysis.tabResearchHint,
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
  const [refreshing, setRefreshing] = useState(false);
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
  const [v2Score, setV2Score] = useState<V2ScoreResponse | null>(null);
  const [v2UnavailableReason, setV2UnavailableReason] = useState<V2UnavailableReason | null>(null);
  const [tradePlan, setTradePlan] = useState<AnalyzeTradePlan | null>(null);
  const [delta, setDelta] = useState<AnalyzeDelta | null>(null);
  const [freshness, setFreshness] = useState<AnalyzeFreshness | null>(null);
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
  const notesSyncedRef = useRef(initialNotes);

  // Sync notes from parent without re-fetching analysis
  useEffect(() => {
    if (initialNotes !== notesSyncedRef.current) {
      notesSyncedRef.current = initialNotes;
      setNotes(initialNotes);
    }
  }, [initialNotes]);

  useEffect(() => {
    if (!symbol) return;

    const gen = ++loadGenRef.current;
    const ac = new AbortController();
    const cacheKey = analysisCacheKey(symbol, bucket);

    setError(null);
    setTab("overview");
    setInsightsOpen(false);
    setBucketFit(null);
    setBucketFitLoading(false);
    setReport(null);
    setReportError(null);
    setReportMsg(null);
    setDiagnostics(null);
    setDiagnosticsError(null);
    setUnifiedRisk(null);
    setRiskError(null);
    diagnosticsOkRef.current = null;
    riskOkRef.current = null;
    setInsightsRetryTick(0);
    setV2UnavailableReason(null);

    const cached = getAnalysisCache(cacheKey);
    if (cached?.base) {
      setData(cached.base);
      setV2Score(cached.v2 ?? null);
      if (cached.v2?.position_sizing) setPositionSizing(cached.v2.position_sizing);
      else setPositionSizing(null);
      setFreshness(cached.freshness ?? { status: "cached", served_from: "client" });
      setLoading(false);
    } else {
      setData(null);
      setV2Score(null);
      setPositionSizing(null);
      setTradePlan(null);
      setDelta(null);
      setFreshness(null);
      setLoading(true);
    }

    performance.mark(`analyze-snapshot-start-${symbol}`);

    void (async () => {
      try {
        // Snapshot paint (best-effort)
        try {
          const snap = await getAnalyzeSnapshot(symbol, bucket, { signal: ac.signal });
          if (gen !== loadGenRef.current) return;
          if (snap.base) {
            applyCorePayload(
              setData,
              setV2Score,
              setPositionSizing,
              setTradePlan,
              setDelta,
              setFreshness,
              setV2UnavailableReason,
              snap
            );
            setLoading(false);
            performance.mark(`analyze-snapshot-paint-${symbol}`);
            try {
              performance.measure(
                `analyze-snapshot-${symbol}`,
                `analyze-snapshot-start-${symbol}`,
                `analyze-snapshot-paint-${symbol}`
              );
            } catch {
              /* ignore */
            }
          }
        } catch {
          /* snapshot miss is fine */
        }

        if (gen !== loadGenRef.current) return;
        setRefreshing(true);
        const core = await getAnalyzeCore(symbol, bucket, { signal: ac.signal });
        if (gen !== loadGenRef.current) return;
        if (!core.base) {
          throw new Error(core.error || tRef.current.analysis.failed);
        }
        applyCorePayload(
          setData,
          setV2Score,
          setPositionSizing,
          setTradePlan,
          setDelta,
          setFreshness,
          setV2UnavailableReason,
          core
        );
        if (!core.v2) {
          setV2UnavailableReason("error");
        }
        setAnalysisCache(cacheKey, {
          base: core.base,
          v2: core.v2 ?? null,
          freshness: core.freshness,
        });
        performance.mark(`analyze-core-settle-${symbol}`);
        try {
          performance.measure(
            `analyze-core-${symbol}`,
            `analyze-snapshot-start-${symbol}`,
            `analyze-core-settle-${symbol}`
          );
        } catch {
          /* ignore */
        }
      } catch (err) {
        if (ac.signal.aborted || gen !== loadGenRef.current || isAbortError(err)) return;
        if (!getAnalysisCache(cacheKey)?.base) {
          setError(explainAnalysisLoadError(err, tRef.current, symbol));
          setData(null);
        }
        setV2UnavailableReason(parseV2FetchError(err));
      } finally {
        if (gen === loadGenRef.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    })();

    return () => ac.abort();
  }, [symbol, bucket, tRef]);

  // Lazy bucket-fit when sidebar needs dual-sleeve and scores are empty
  useEffect(() => {
    if (!data || data.symbol !== symbol) return;
    const scores = bucketFit?.scores ?? data.bucket_fit?.scores ?? {};
    if (Object.keys(scores).length > 0) return;
    // Only fetch when insights rail is open or on desktop (sidebar always visible on lg)
    // Defer until after core settled
    if (loading || refreshing) return;

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
  }, [data, symbol, bucketFit?.scores, loading, refreshing]);

  const retryDiagnostics = useCallback(() => {
    diagnosticsOkRef.current = null;
    setInsightsRetryTick((n) => n + 1);
  }, []);

  const retryUnifiedRisk = useCallback(() => {
    riskOkRef.current = null;
    setInsightsRetryTick((n) => n + 1);
  }, []);

  const activeTab = normalizeAnalysisTab(tab);

  useEffect(() => {
    if (!data || data.symbol !== symbol) return;
    const b = (bucket ?? data.assigned_bucket) as Bucket;
    const cacheKey = `${symbol}:${b}`;
    const ac = new AbortController();

    if (activeTab === "evidence" && diagnosticsOkRef.current !== cacheKey) {
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

    if (activeTab === "risk" && riskOkRef.current !== cacheKey) {
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
  }, [activeTab, data, symbol, bucket, insightsRetryTick, tRef]);

  useEffect(() => {
    if (activeTab !== "research" || !symbol) return;
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
  }, [activeTab, symbol, report]);

  const refresh = useCallback(async () => {
    if (!symbol) return;
    const gen = ++loadGenRef.current;
    const ac = new AbortController();
    const cacheKey = analysisCacheKey(symbol, bucket);
    clearAnalysisCache(cacheKey);
    setRefreshing(true);
    setError(null);
    setBucketFit(null);
    try {
      const core = await getAnalyzeCore(symbol, bucket, {
        signal: ac.signal,
        refresh: true,
      });
      if (gen !== loadGenRef.current) return;
      if (!core.base) throw new Error(core.error || tRef.current.analysis.failed);
      applyCorePayload(
        setData,
        setV2Score,
        setPositionSizing,
        setTradePlan,
        setDelta,
        setFreshness,
        setV2UnavailableReason,
        core
      );
      setAnalysisCache(cacheKey, {
        base: core.base,
        v2: core.v2 ?? null,
        freshness: core.freshness,
      });
    } catch (err) {
      if (ac.signal.aborted || gen !== loadGenRef.current || isAbortError(err)) return;
      setError(explainAnalysisLoadError(err, tRef.current, symbol));
    } finally {
      if (gen === loadGenRef.current) {
        setLoading(false);
        setRefreshing(false);
      }
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
    return <p className="p-6 text-sm text-zinc-500">{t.analysis.selectSymbol}</p>;
  }

  const ready = data && data.symbol === symbol;

  if (!ready) {
    if (error) {
      return (
        <div
          className={
            embedded ? "flex flex-1 items-start p-6" : "analysis-shell p-6"
          }
        >
          <ErrorState
            message={`${t.analysis.fetchFailedTitle}. ${error}`}
            onRetry={() => void refresh()}
          />
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
            >
              {t.analysis.openInsights}
            </button>
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={loading || refreshing}
              className="btn-ghost shrink-0 px-3 py-1.5 text-sm"
            >
              {loading || refreshing ? "…" : t.common.refresh}
            </button>
          </div>
        </div>

        <AnalysisHeaderStats
          price={data.price}
          changePct1d={(() => {
            const n = Number(data.metrics?.change_pct_1d);
            return Number.isFinite(n) ? n : null;
          })()}
          recommendation={
            v2Score?.recommendation
              ? null
              : ((data.metrics?.recommendation as string) ?? null)
          }
          bucketLabel={bucketMeta[data.assigned_bucket as Bucket]?.label ?? data.assigned_bucket}
          score={display.score}
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
          {activeTab === "overview" && (
            <div
              id={analysisPanelId("overview")}
              role="tabpanel"
              aria-labelledby="analysis-tab-overview"
              className="analysis-overview"
            >
              {refreshing && !v2Score && (
                <p className="text-xs text-zinc-500">{t.analysis.loadingQuantV2}</p>
              )}
              {!refreshing && !v2Score && v2UnavailableReason && (
                <V2FallbackBanner reason={v2UnavailableReason} />
              )}
              <div className="analysis-glass-panel analysis-glass-panel--chart analysis-overview-chart">
                <PriceChart
                  ohlc={data.ohlc}
                  priceHistoryLastDate={data.price_history_last_date}
                  priceHistoryIsStale={data.price_history_is_stale}
                  priceHistoryRefreshedAt={data.price_history_refreshed_at}
                  heightClassName="h-[min(17rem,38vh)]"
                />
              </div>
              <div className="analysis-overview-grid">
                <div className="analysis-overview-main min-w-0">
                  <DecisionOverviewLead
                    v2={v2Score}
                    score={display.score}
                    riskLabel={riskLabel(String(display.riskLevel))}
                    tradePlan={tradePlan}
                    freshness={freshness}
                    refreshing={refreshing}
                  />
                </div>
                <div className="analysis-glass-panel analysis-overview-side">
                  <div className="analysis-section analysis-section--flush analysis-overview-side__body">
                    <h3 className="analysis-section__title">{t.analysis.positionSizing}</h3>
                    <PositionSizingBlock
                      sizing={positionSizing ?? v2Score?.position_sizing ?? null}
                      loading={refreshing && !positionSizing}
                      error={null}
                    />
                  </div>
                  {data.valuation_warnings?.length > 0 && (
                    <>
                      <div className="analysis-side-divider" />
                      <div className="analysis-section analysis-section--flush">
                        <h3 className="analysis-section__title">{t.analysis.tabValuation}</h3>
                        <ul className="space-y-1 text-sm text-amber-200/90">
                          {data.valuation_warnings.map((w, idx) => (
                            <li key={`${idx}-${w}`}>{w}</li>
                          ))}
                        </ul>
                      </div>
                    </>
                  )}
                </div>
              </div>
              <DecisionOverviewDetails
                v2={v2Score}
                tradePlan={tradePlan}
                delta={delta}
              />
            </div>
          )}

          {activeTab === "drivers" && (
            <div
              id={analysisPanelId("drivers")}
              role="tabpanel"
              aria-labelledby="analysis-tab-drivers"
              className="space-y-4"
            >
              {refreshing && <p className="text-xs text-zinc-500">{t.analysis.loadingQuantV2}</p>}
              {v2Score ? (
                <>
                  <FactorAttributionTable factors={v2Score.factors} />
                  {v2Score.parity_delta != null && (
                    <p className="text-xs text-zinc-500">
                      {t.scanDrawer.parityDelta}: {v2Score.parity_delta.toFixed(2)}
                    </p>
                  )}
                  <ScoreBreakdown
                    signals={data.signals}
                    className="analysis-chart-box h-64 w-full p-3"
                  />
                  {v2Score.valuation ? (
                    <ValuationBlock data={v2Score.valuation} />
                  ) : (
                    <p className="text-sm text-zinc-500">{t.analysis.valuationUnavailable}</p>
                  )}
                  {v2Score.earnings_setup && Object.keys(v2Score.earnings_setup).length > 0 && (
                    <div className="analysis-section">
                      <h3 className="analysis-section__title">{t.analysis.earningsSetup}</h3>
                      <pre className="overflow-x-auto text-[11px] text-zinc-400">
                        {JSON.stringify(v2Score.earnings_setup, null, 2)}
                      </pre>
                    </div>
                  )}
                </>
              ) : (
                <ScoreBreakdown
                  signals={data.signals}
                  className="analysis-chart-box h-80 w-full p-3"
                />
              )}
            </div>
          )}

          {activeTab === "risk" && (
            <div
              id={analysisPanelId("risk")}
              role="tabpanel"
              aria-labelledby="analysis-tab-risk"
              className="space-y-4"
            >
              <UnifiedRiskPanel
                data={unifiedRisk}
                loading={riskLoading}
                error={riskError}
                onRetry={riskError ? retryUnifiedRisk : undefined}
              />
              <div className="analysis-section">
                <h3 className="analysis-section__title">{t.analysis.positionSizing}</h3>
                <PositionSizingBlock
                  sizing={positionSizing ?? v2Score?.position_sizing ?? null}
                  loading={false}
                  error={null}
                />
              </div>
              {v2Score?.portfolio_impact && (
                <div className="analysis-section">
                  <h3 className="analysis-section__title">{t.analysis.portfolioImpact}</h3>
                  <pre className="overflow-x-auto text-[11px] text-zinc-400">
                    {JSON.stringify(v2Score.portfolio_impact, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}

          {activeTab === "evidence" && (
            <div
              id={analysisPanelId("evidence")}
              role="tabpanel"
              aria-labelledby="analysis-tab-evidence"
              className="space-y-4"
            >
              <ResearchWarning />
              {v2Score?.similar_signal ? (
                <SimilarSignalBlock data={v2Score.similar_signal} />
              ) : (
                <p className="text-sm text-zinc-500">{t.quant.similarInsufficient}</p>
              )}
              <DiagnosticsPanel
                data={diagnostics}
                loading={diagnosticsLoading}
                error={diagnosticsError}
                onRetry={diagnosticsError ? retryDiagnostics : undefined}
              />
              <BacktestPanel symbol={data.symbol} bucket={data.assigned_bucket} />
            </div>
          )}

          {activeTab === "research" && (
            <div
              id={analysisPanelId("research")}
              role="tabpanel"
              aria-labelledby="analysis-tab-research"
              className="space-y-4"
            >
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
              <div className="analysis-glass-panel analysis-block">
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
              <NotFinancialAdviceFooter llmNote />
            </div>
          )}
        </div>

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
      </div>

      {insightsOpen && (
        <div className="analysis-insights-backdrop lg:hidden" role="presentation">
          <button
            type="button"
            className="analysis-insights-backdrop-hit"
            aria-label={t.common.close}
            onClick={() => setInsightsOpen(false)}
          />
          <div
            className="analysis-insights-sheet"
            role="dialog"
            aria-modal="true"
            aria-label={t.analysis.insightsPanelTitle}
          >
            <div className="analysis-insights-sheet-header">
              <h3 className="text-sm font-semibold text-zinc-100">
                {t.analysis.insightsPanelTitle}
              </h3>
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
