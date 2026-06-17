"use client";

import {
  getPortfolioFactorExposure,
  getPortfolioRebalancePreview,
  getPortfolioSummary,
  getWatchlist,
  optimizePortfolio,
  runPortfolioPolicyBacktest,
  runV2PortfolioBacktest,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import type {
  FactorExposureResponse,
  PortfolioOptimizeResponse,
  PortfolioPolicyBacktestResponse,
  PortfolioSourceType,
  PortfolioSummaryResponse,
  RebalancePreviewResponse,
} from "@/lib/types";
import {
  buildExposureCacheKey,
  buildRebalanceHoldings,
  parseSymbols,
  type PortfolioSleeve,
} from "@/lib/portfolioUtils";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppTabBar, AppTabButton } from "./AppTabs";
import { PageHeader } from "@/components/ui/PageHeader";
import { PageContainer } from "@/components/ui/PageContainer";
import { PortfolioSourceBar } from "./portfolio/PortfolioSourceBar";
import { PortfolioOverviewTab } from "./portfolio/PortfolioOverviewTab";
import { PortfolioRebalanceTab } from "./portfolio/PortfolioRebalanceTab";
import { PortfolioRiskTab } from "./portfolio/PortfolioRiskTab";
import { PortfolioBacktestTab } from "./portfolio/PortfolioBacktestTab";
import { PortfolioAdvancedTab } from "./portfolio/PortfolioAdvancedTab";

type PanelTab = "overview" | "rebalance" | "risk" | "backtest" | "advanced";

export function PortfolioPage() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [panel, setPanel] = useState<PanelTab>("overview");
  const [source, setSource] = useState<PortfolioSourceType>("current");
  const [symbolInput, setSymbolInput] = useState("");
  const [watchlistSyms, setWatchlistSyms] = useState<string[]>([]);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);

  const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  const [objective, setObjective] = useState<
    "max_sharpe" | "min_vol" | "risk_parity" | "target_return" | "kelly"
  >("max_sharpe");
  const [lookback, setLookback] = useState<"6mo" | "1y" | "2y" | "3y" | "5y">("1y");
  const [maxWeight, setMaxWeight] = useState("0.35");
  const [cashBuffer, setCashBuffer] = useState("0.05");
  const [targetReturn, setTargetReturn] = useState("0.10");
  const [minTrade, setMinTrade] = useState("0");
  const [fractionalShares, setFractionalShares] = useState(true);

  const [optimizeLoading, setOptimizeLoading] = useState(false);
  const [optimizeError, setOptimizeError] = useState<string | null>(null);
  const [optimizeResult, setOptimizeResult] = useState<PortfolioOptimizeResponse | null>(null);

  const [rebalanceLoading, setRebalanceLoading] = useState(false);
  const [rebalanceError, setRebalanceError] = useState<string | null>(null);
  const [rebalanceResult, setRebalanceResult] = useState<RebalancePreviewResponse | null>(null);

  const [exposureResult, setExposureResult] = useState<FactorExposureResponse | null>(null);
  const [exposureResultKey, setExposureResultKey] = useState<string | null>(null);
  const [exposureLoading, setExposureLoading] = useState(false);
  const [exposureError, setExposureError] = useState<string | null>(null);
  const exposureCacheRef = useRef<{ key: string; data: FactorExposureResponse } | null>(null);

  const [policy, setPolicy] = useState<"equal_weight" | "inverse_vol" | "top_n_momentum">("equal_weight");
  const [rebalanceFreq, setRebalanceFreq] = useState<"weekly" | "monthly">("monthly");
  const [sleeve, setSleeve] = useState<PortfolioSleeve>("penny");
  const [initialCapital, setInitialCapital] = useState("100000");
  const [institutional, setInstitutional] = useState(false);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<PortfolioPolicyBacktestResponse | null>(null);

  const benchmark = "SPY";

  const activeSymbols = useMemo(() => {
    if (source === "current" && summary?.positions.length) {
      return summary.positions.map((p) => p.symbol);
    }
    if (source === "watchlist" && watchlistSyms.length) {
      return watchlistSyms;
    }
    return parseSymbols(symbolInput);
  }, [source, summary, watchlistSyms, symbolInput]);

  const exposureKey = useMemo(
    () => buildExposureCacheKey({ symbols: activeSymbols, lookback, benchmark }),
    [activeSymbols, lookback, benchmark]
  );
  const exposureStale =
    exposureResult != null && exposureResultKey != null && exposureResultKey !== exposureKey;

  const isHypothetical = source !== "current";

  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    setSummaryError(null);
    try {
      const res = await getPortfolioSummary();
      setSummary(res);
      if (source === "current" && res.positions.length) {
        setSymbolInput(res.positions.map((p) => p.symbol).join(", "));
      }
    } catch (err) {
      setSummaryError(parseApiError(err, tRef.current.portfolio.summaryFailed));
    } finally {
      setSummaryLoading(false);
    }
  }, [source, tRef]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    getWatchlist()
      .then((items) => {
        setWatchlistSyms(items.map((i) => i.symbol));
        setWatchlistError(null);
      })
      .catch((err) => {
        setWatchlistError(parseApiError(err, tRef.current.portfolio.watchlistFailed));
      });
  }, [tRef]);

  useEffect(() => {
    if (source === "watchlist" && watchlistSyms.length) {
      setSymbolInput(watchlistSyms.join(", "));
    }
  }, [source, watchlistSyms]);

  const loadWatchlist = useCallback(() => {
    if (watchlistSyms.length) setSymbolInput(watchlistSyms.join(", "));
  }, [watchlistSyms]);

  const runExposure = useCallback(async () => {
    if (activeSymbols.length < 2) {
      setExposureError(tRef.current.portfolio.needTwoSymbols);
      return;
    }
    if (exposureCacheRef.current?.key === exposureKey) {
      setExposureResult(exposureCacheRef.current.data);
      setExposureResultKey(exposureKey);
      setExposureError(null);
      return;
    }
    setExposureLoading(true);
    setExposureError(null);
    try {
      const res = await getPortfolioFactorExposure({
        symbols: activeSymbols,
        benchmark,
        lookback_period: lookback,
      });
      exposureCacheRef.current = { key: exposureKey, data: res };
      setExposureResult(res);
      setExposureResultKey(exposureKey);
    } catch (err) {
      setExposureError(parseApiError(err, tRef.current.portfolio.exposureFailed));
    } finally {
      setExposureLoading(false);
    }
  }, [activeSymbols, exposureKey, lookback, benchmark, tRef]);

  useEffect(() => {
    if (panel !== "risk" || activeSymbols.length < 2) return;
    if (exposureCacheRef.current?.key === exposureKey) {
      if (exposureResultKey !== exposureKey) {
        setExposureResult(exposureCacheRef.current.data);
        setExposureResultKey(exposureKey);
      }
      return;
    }
    void runExposure();
  }, [panel, exposureKey, activeSymbols.length, runExposure, exposureResultKey]);

  const runOptimize = async () => {
    if (activeSymbols.length < 2) {
      setOptimizeError(t.portfolio.needTwoSymbols);
      return;
    }
    setOptimizeLoading(true);
    setOptimizeError(null);
    try {
      const res = await optimizePortfolio({
        symbols: activeSymbols,
        objective,
        lookback_period: lookback,
        max_weight: Number(maxWeight) || 0.35,
        cash_buffer: Number(cashBuffer) || 0.05,
        target_return: objective === "target_return" ? Number(targetReturn) : undefined,
        kelly_overlay: objective === "kelly",
      });
      setOptimizeResult(res);
    } catch (err) {
      setOptimizeError(parseApiError(err, t.portfolio.optimizeFailed));
    } finally {
      setOptimizeLoading(false);
    }
  };

  const runRebalancePreview = async () => {
    if (!optimizeResult || !summary) {
      setRebalanceError(t.portfolio.rebalanceNeedsOptimize);
      return;
    }
    setRebalanceLoading(true);
    setRebalanceError(null);
    try {
      const target_weights = Object.fromEntries(
        optimizeResult.weights.map((w) => [w.symbol, w.weight])
      );
      const res = await getPortfolioRebalancePreview({
        holdings: buildRebalanceHoldings(activeSymbols, summary),
        target_weights,
        cash: summary.cash,
        cash_reserve: Number(cashBuffer) || 0.05,
        min_trade_amount: Number(minTrade) || 0,
        fractional_shares: fractionalShares,
      });
      setRebalanceResult(res);
    } catch (err) {
      setRebalanceError(parseApiError(err, t.portfolio.rebalanceFailed));
    } finally {
      setRebalanceLoading(false);
    }
  };

  const runBacktest = async () => {
    if (activeSymbols.length < 2) {
      setBacktestError(t.portfolio.needTwoSymbols);
      return;
    }
    setBacktestLoading(true);
    setBacktestError(null);
    try {
      const apiSleeve = sleeve === "custom" ? "penny" : sleeve;
      const payload = {
        symbols: activeSymbols,
        policy,
        rebalance: rebalanceFreq,
        lookback_period: lookback,
        initial_capital: Number(initialCapital) || 100_000,
        max_weight: Number(maxWeight) || 0.35,
        cash_buffer: Number(cashBuffer) || 0.05,
        institutional,
        sleeve: apiSleeve as "penny" | "compounder",
        use_universe_pit: institutional,
      };
      const res = institutional
        ? await runV2PortfolioBacktest(payload)
        : await runPortfolioPolicyBacktest(payload);
      setBacktestResult(res);
    } catch (err) {
      setBacktestError(parseApiError(err, t.portfolio.policyFailed));
    } finally {
      setBacktestLoading(false);
    }
  };

  return (
    <PageContainer className="space-y-4">
      <PageHeader
        title={t.portfolio.title}
        subtitle={t.portfolio.subtitleWorkflow}
        actions={
          <AppTabBar aria-label={t.portfolio.toolsAria}>
            <AppTabButton active={panel === "overview"} onClick={() => setPanel("overview")}>
              {t.portfolio.tabOverview}
            </AppTabButton>
            <AppTabButton active={panel === "rebalance"} onClick={() => setPanel("rebalance")}>
              {t.portfolio.tabRebalance}
            </AppTabButton>
            <AppTabButton active={panel === "risk"} onClick={() => setPanel("risk")}>
              {t.portfolio.tabRisk}
            </AppTabButton>
            <AppTabButton active={panel === "backtest"} onClick={() => setPanel("backtest")}>
              {t.portfolio.tabBacktest}
            </AppTabButton>
            <AppTabButton active={panel === "advanced"} onClick={() => setPanel("advanced")}>
              {t.portfolio.tabAdvanced}
            </AppTabButton>
          </AppTabBar>
        }
      />

      <PortfolioSourceBar
        source={source}
        onSourceChange={setSource}
        symbolInput={symbolInput}
        onSymbolInputChange={setSymbolInput}
        onLoadWatchlist={loadWatchlist}
        watchlistSyms={watchlistSyms}
        summary={summary}
        summaryLoading={summaryLoading}
        summaryError={summaryError ?? watchlistError}
        onRetrySummary={() => void loadSummary()}
        isHypothetical={isHypothetical}
      />

      {panel === "overview" && (
        <PortfolioOverviewTab
          summary={summary}
          loading={summaryLoading && !summary}
          refreshing={summaryLoading && !!summary}
          error={summaryError}
          onRetry={() => void loadSummary()}
        />
      )}

      {panel === "rebalance" && (
        <PortfolioRebalanceTab
          symbols={activeSymbols}
          summary={summary}
          objective={objective}
          onObjectiveChange={setObjective}
          lookback={lookback}
          onLookbackChange={setLookback}
          maxWeight={maxWeight}
          onMaxWeightChange={setMaxWeight}
          cashBuffer={cashBuffer}
          onCashBufferChange={setCashBuffer}
          targetReturn={targetReturn}
          onTargetReturnChange={setTargetReturn}
          minTrade={minTrade}
          onMinTradeChange={setMinTrade}
          fractionalShares={fractionalShares}
          onFractionalSharesChange={setFractionalShares}
          optimizeLoading={optimizeLoading}
          optimizeError={optimizeError}
          optimizeResult={optimizeResult}
          onRunOptimize={() => void runOptimize()}
          rebalanceLoading={rebalanceLoading}
          rebalanceError={rebalanceError}
          rebalanceResult={rebalanceResult}
          onRunRebalance={() => void runRebalancePreview()}
        />
      )}

      {panel === "risk" && (
        <PortfolioRiskTab
          summary={summary}
          exposureResult={exposureResult}
          exposureLoading={exposureLoading}
          exposureError={exposureError}
          exposureStale={exposureStale}
          exposureKey={exposureKey}
          onRunExposure={() => void runExposure()}
          symbolsCount={activeSymbols.length}
        />
      )}

      {panel === "backtest" && (
        <PortfolioBacktestTab
          symbolsCount={activeSymbols.length}
          policy={policy}
          onPolicyChange={setPolicy}
          rebalance={rebalanceFreq}
          onRebalanceChange={setRebalanceFreq}
          lookback={lookback}
          onLookbackChange={setLookback}
          sleeve={sleeve}
          onSleeveChange={setSleeve}
          initialCapital={initialCapital}
          onInitialCapitalChange={setInitialCapital}
          institutional={institutional}
          onInstitutionalChange={setInstitutional}
          loading={backtestLoading && !backtestResult}
          refreshing={backtestLoading && !!backtestResult}
          error={backtestError}
          result={backtestResult}
          onRun={() => void runBacktest()}
          onRetry={() => void runBacktest()}
        />
      )}

      {panel === "advanced" && <PortfolioAdvancedTab symbols={activeSymbols} />}

      <p className="text-xs text-zinc-600">{t.portfolio.quantHint}</p>
    </PageContainer>
  );
}
