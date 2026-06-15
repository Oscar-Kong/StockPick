// Tabbed scan detail drawer — lazy-loads heavy endpoints per tab.
"use client";

import {
  getResearchReport,
  getStock,
  getSymbolDiagnostics,
  getV2Score,
  getV2SimilarSignal,
  getV2UnifiedRisk,
} from "@/lib/api";
import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { RiskBadge } from "@/components/badges/RiskBadge";
import { ScoreBadge } from "@/components/badges/ScoreBadge";
import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { FactorAttributionTable } from "@/components/quant/FactorAttributionTable";
import { BacktestPanel } from "./BacktestPanel";
import { DataQualityBadge } from "./DataQualityBadge";
import { DiagnosticsPanel } from "./DiagnosticsPanel";
import { ResearchReport } from "./ResearchReport";
import { ScanPickSummaryCell } from "./ScanPickSummaryCell";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { UnifiedRiskPanel } from "./UnifiedRiskPanel";
import { ValuationBadges } from "./ValuationBadges";
import { DetailDrawer } from "./ui/DetailDrawer";
import { EmptyState } from "./ui/EmptyState";
import { StatTile } from "./ui/StatTile";
import { NotFinancialAdviceFooter } from "./ui/NotFinancialAdviceFooter";
import { ResearchWarning } from "./ui/ResearchWarning";
import { SimilarSignalBlock } from "./SimilarSignalBlock";
import type {
  Bucket,
  SimilarSignalV2,
  StockDetail,
  StockResearchReport,
  StockResult,
  SymbolDiagnosticsResponse,
  UnifiedRiskV2,
  V2ScoreResponse,
} from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const DRAWER_TABS = [
  "summary",
  "factors",
  "risk",
  "diagnostics",
  "similar",
  "backtest",
  "report",
] as const;

type DrawerTab = (typeof DRAWER_TABS)[number];

interface StockDetailDrawerProps {
  stock: StockResult | null;
  bucket: Bucket;
  scoringEngineUsed?: boolean | null;
  onClose: () => void;
}

export function StockDetailDrawer({
  stock,
  bucket,
  scoringEngineUsed,
  onClose,
}: StockDetailDrawerProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [tab, setTab] = useState<DrawerTab>("summary");
  const [detail, setDetail] = useState<StockDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [v2Score, setV2Score] = useState<V2ScoreResponse | null>(null);
  const [v2Loading, setV2Loading] = useState(false);
  const [v2Error, setV2Error] = useState<string | null>(null);

  const [risk, setRisk] = useState<UnifiedRiskV2 | null>(null);
  const [riskLoading, setRiskLoading] = useState(false);
  const [riskError, setRiskError] = useState<string | null>(null);

  const [diagnostics, setDiagnostics] = useState<SymbolDiagnosticsResponse | null>(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [diagError, setDiagError] = useState<string | null>(null);

  const [similar, setSimilar] = useState<SimilarSignalV2 | null>(null);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarError, setSimilarError] = useState<string | null>(null);

  const [report, setReport] = useState<StockResearchReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);

  const loadedRef = useRef<Set<string>>(new Set());

  const tabs = useMemo(
    () =>
      DRAWER_TABS.map((id) => ({
        id,
        label: t.scanDrawer.tabs[id],
      })),
    [t.scanDrawer.tabs]
  );

  useEffect(() => {
    if (!stock) return;
    setTab("summary");
    setDetail(null);
    loadedRef.current = new Set();
    setV2Score(null);
    setRisk(null);
    setDiagnostics(null);
    setSimilar(null);
    setReport(null);
    setDetailLoading(true);
    getStock(stock.symbol, bucket, false)
      .then(setDetail)
      .catch(() => setDetail(null))
      .finally(() => setDetailLoading(false));
  }, [stock, bucket]);

  const loadTab = useCallback(
    async (tabId: DrawerTab) => {
      if (!stock) return;
      const key = `${stock.symbol}:${tabId}`;
      if (loadedRef.current.has(key)) return;
      loadedRef.current.add(key);

      if (tabId === "factors") {
        setV2Loading(true);
        setV2Error(null);
        try {
          setV2Score(await getV2Score(stock.symbol, bucket));
        } catch (e) {
          setV2Error(e instanceof Error ? e.message : tRef.current.scanDrawer.loadFailed);
        } finally {
          setV2Loading(false);
        }
      }
      if (tabId === "risk") {
        setRiskLoading(true);
        setRiskError(null);
        try {
          setRisk(await getV2UnifiedRisk(stock.symbol, bucket));
        } catch (e) {
          setRiskError(e instanceof Error ? e.message : tRef.current.scanDrawer.loadFailed);
        } finally {
          setRiskLoading(false);
        }
      }
      if (tabId === "diagnostics") {
        setDiagLoading(true);
        setDiagError(null);
        try {
          setDiagnostics(await getSymbolDiagnostics(stock.symbol));
        } catch (e) {
          setDiagError(e instanceof Error ? e.message : tRef.current.scanDrawer.loadFailed);
        } finally {
          setDiagLoading(false);
        }
      }
      if (tabId === "similar") {
        setSimilarLoading(true);
        setSimilarError(null);
        try {
          const res = await getV2SimilarSignal(stock.symbol, bucket);
          setSimilar(res);
        } catch (e) {
          setSimilarError(e instanceof Error ? e.message : tRef.current.scanDrawer.loadFailed);
        } finally {
          setSimilarLoading(false);
        }
      }
      if (tabId === "report") {
        setReportLoading(true);
        setReportError(null);
        try {
          setReport(await getResearchReport(stock.symbol, bucket));
        } catch (e) {
          setReportError(e instanceof Error ? e.message : tRef.current.scanDrawer.loadFailed);
        } finally {
          setReportLoading(false);
        }
      }
    },
    [stock, bucket]
  );

  useEffect(() => {
    if (!stock || tab === "summary" || tab === "backtest") return;
    void loadTab(tab);
  }, [tab, stock, loadTab]);

  if (!stock) return null;

  const scoreSource =
    scoringEngineUsed === true
      ? "scoring_engine_v2"
      : scoringEngineUsed === false
        ? "legacy_screener"
        : v2Score
          ? "scoring_engine_v2"
          : "legacy_screener";

  const topPositive = [...stock.signals]
    .filter((s) => s.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, 3);
  const topWarnings = stock.signals
    .filter((s) => s.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution)
    .slice(0, 2);

  return (
    <DetailDrawer
      open
      title={stock.symbol}
      subtitle={`$${stock.price.toFixed(2)} · ${t.scanDrawer.bucket} ${bucket}`}
      tabs={tabs}
      activeTab={tab}
      onTabChange={(id) => setTab(id as DrawerTab)}
      onClose={onClose}
      loading={detailLoading && tab === "summary"}
    >
      {tab === "summary" && (
        <div className="space-y-4">
          <dl className="grid gap-3 sm:grid-cols-2">
            <StatTile
              label={t.common.score}
              value={<ScoreBadge score={stock.score} />}
            />
            <StatTile
              label={t.analysis.scoreSourceLabel}
              value={<ScoreSourceBadge source={scoreSource} />}
            />
            <StatTile
              label={t.analysis.riskLabel}
              value={<RiskBadge level={stock.risk_level} />}
            />
            {v2Score?.recommendation && (
              <StatTile
                label={t.scanDrawer.recommendationLabel}
                value={
                  <RecommendationBadge recommendation={v2Score.recommendation.recommendation} />
                }
              />
            )}
          </dl>
          <ValuationBadges
            warnings={detail?.valuation_warnings ?? stock.valuation_warnings}
            earningsSoon={detail?.earnings_soon ?? stock.earnings_soon}
            earningsDate={detail?.earnings_date ?? stock.earnings_date}
            daysUntil={detail?.days_until_earnings ?? stock.days_until_earnings ?? undefined}
          />
          <DataQualityBadge
            score={detail?.data_quality_score}
            flags={(stock.metrics?.data_quality_flags as string[] | undefined) ?? undefined}
          />
          <ScanPickSummaryCell stock={stock} variant="drawer" />
          {topPositive.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-zinc-500">{t.scanDrawer.topFactors}</h3>
              <ul className="text-xs text-zinc-400">
                {topPositive.map((s) => (
                  <li key={s.name}>
                    {s.name} (+{s.contribution.toFixed(1)})
                  </li>
                ))}
              </ul>
            </div>
          )}
          {topWarnings.length > 0 && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase text-zinc-500">{t.scanDrawer.warnings}</h3>
              <ul className="text-xs text-amber-200/80">
                {topWarnings.map((s) => (
                  <li key={s.name}>
                    {s.name} ({s.contribution.toFixed(1)})
                  </li>
                ))}
              </ul>
            </div>
          )}
          <Link
            href={`/workspace?symbol=${encodeURIComponent(stock.symbol)}`}
            className="btn-primary inline-block px-3 py-1.5 text-xs"
          >
            {t.scanDrawer.openWorkspace}
          </Link>
        </div>
      )}

      {tab === "factors" && (
        <div className="space-y-4">
          {v2Loading && <p className="text-xs text-zinc-500">{t.common.loading}</p>}
          {v2Error && (
            <EmptyState message={v2Error} action={<ScoreBreakdown signals={stock.signals} className="h-64" />} />
          )}
          {v2Score && (
            <>
              <FactorAttributionTable factors={v2Score.factors} />
              {v2Score.parity_delta != null && (
                <p className="text-xs text-zinc-500">
                  {t.scanDrawer.parityDelta}: {v2Score.parity_delta.toFixed(2)}
                </p>
              )}
            </>
          )}
          {!v2Loading && !v2Score && !v2Error && (
            <ScoreBreakdown signals={stock.signals} className="h-64" />
          )}
        </div>
      )}

      {tab === "risk" && (
        <UnifiedRiskPanel
          data={risk}
          loading={riskLoading}
          error={riskError}
          onRetry={riskError ? () => {
            loadedRef.current.delete(`${stock.symbol}:risk`);
            void loadTab("risk");
          } : undefined}
        />
      )}

      {tab === "diagnostics" && (
        <DiagnosticsPanel
          data={diagnostics}
          loading={diagLoading}
          error={diagError}
          onRetry={diagError ? () => {
            loadedRef.current.delete(`${stock.symbol}:diagnostics`);
            void loadTab("diagnostics");
          } : undefined}
        />
      )}

      {tab === "similar" && (
        <div className="space-y-3">
          <ResearchWarning />
          {similarLoading && <p className="text-xs text-zinc-500">{t.common.loading}</p>}
          {similarError && <EmptyState message={similarError} />}
          {similar && <SimilarSignalBlock data={similar} />}
        </div>
      )}

      {tab === "backtest" && (
        <BacktestPanel symbol={stock.symbol} bucket={stock.bucket} embedded={detail?.backtest ?? undefined} />
      )}

      {tab === "report" && (
        <div className="space-y-3">
          <ResearchReport report={report} loading={reportLoading} error={reportError} />
          <NotFinancialAdviceFooter llmNote />
        </div>
      )}
    </DetailDrawer>
  );
}
