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
import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { GhostButton } from "@/components/ui/buttons";
import { PortfolioRebalanceTab } from "@/components/portfolio/PortfolioRebalanceTab";
import { PortfolioRiskTab } from "@/components/portfolio/PortfolioRiskTab";
import { PortfolioBacktestTab } from "@/components/portfolio/PortfolioBacktestTab";
import { PortfolioAdvancedTab } from "@/components/portfolio/PortfolioAdvancedTab";
import type { ResearchPanel } from "./usePortfolioTab";

interface PortfolioResearchProps {
  active: boolean;
  holdingSymbols: string[];
  panel: ResearchPanel;
  onPanelChange: (panel: ResearchPanel) => void;
}

export function PortfolioResearch({
  active,
  holdingSymbols,
  panel,
  onPanelChange,
}: PortfolioResearchProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [basketInput, setBasketInput] = useState("");
  const [basketTouched, setBasketTouched] = useState(false);
  const [watchlistSyms, setWatchlistSyms] = useState<string[]>([]);
  const [watchlistError, setWatchlistError] = useState<string | null>(null);
  const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [summaryLoaded, setSummaryLoaded] = useState(false);

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
  const activeSymbols = useMemo(() => parseSymbols(basketInput), [basketInput]);

  const exposureKey = useMemo(
    () => buildExposureCacheKey({ symbols: activeSymbols, lookback, benchmark }),
    [activeSymbols, lookback, benchmark]
  );
  const exposureStale =
    exposureResult != null && exposureResultKey != null && exposureResultKey !== exposureKey;

  useEffect(() => {
    if (!basketTouched && holdingSymbols.length) {
      setBasketInput(holdingSymbols.join(", "));
    }
  }, [holdingSymbols, basketTouched]);

  const loadSummary = useCallback(async () => {
    setSummaryError(null);
    try {
      const res = await getPortfolioSummary();
      setSummary(res);
    } catch (err) {
      setSummaryError(parseApiError(err, tRef.current.portfolio.summaryFailed));
    } finally {
      setSummaryLoaded(true);
    }
  }, [tRef]);

  useEffect(() => {
    if (!active || summaryLoaded) return;
    void loadSummary();
  }, [active, summaryLoaded, loadSummary]);

  useEffect(() => {
    if (!active) return;
    getWatchlist()
      .then((items) => {
        setWatchlistSyms(items.map((i) => i.symbol));
        setWatchlistError(null);
      })
      .catch((err) => {
        setWatchlistError(parseApiError(err, tRef.current.portfolio.watchlistFailed));
      });
  }, [active, tRef]);

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
    if (!active || panel !== "exposure" || activeSymbols.length < 2) return;
    if (exposureCacheRef.current?.key === exposureKey) {
      if (exposureResultKey !== exposureKey) {
        setExposureResult(exposureCacheRef.current.data);
        setExposureResultKey(exposureKey);
      }
      return;
    }
    void runExposure();
  }, [active, panel, exposureKey, activeSymbols.length, runExposure, exposureResultKey]);

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

  const resetBasket = () => {
    setBasketTouched(false);
    setBasketInput(holdingSymbols.join(", "));
  };

  const addFromWatchlist = () => {
    setBasketTouched(true);
    setBasketInput([...new Set([...activeSymbols, ...watchlistSyms])].join(", "));
  };

  if (!active) {
    return <p className="text-sm text-secondary">{t.portfolio.researchInactiveHint}</p>;
  }

  return (
    <div className="space-y-4">
      <section className="portfolio-research-basket surface-card">
        <div className="portfolio-research-basket__header">
          <div>
            <p className="portfolio-source__label">{t.portfolio.researchBasketLabel}</p>
            <p className="portfolio-source__hint">{t.portfolio.researchBasketHint}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <GhostButton type="button" className="text-xs" onClick={resetBasket} disabled={!holdingSymbols.length}>
              {t.portfolio.resetToHoldings}
            </GhostButton>
            {watchlistSyms.length > 0 && (
              <GhostButton type="button" className="text-xs" onClick={addFromWatchlist}>
                {t.portfolio.addFromWatchlist}
              </GhostButton>
            )}
          </div>
        </div>
        <textarea
          id="research-basket-input"
          value={basketInput}
          onChange={(e) => {
            setBasketTouched(true);
            setBasketInput(e.target.value);
          }}
          rows={2}
          placeholder={t.portfolio.symbolsPlaceholder}
          className="portfolio-source__textarea"
        />
        <div className="portfolio-source__chips">
          {watchlistSyms.slice(0, 12).map((sym) => (
            <button
              key={sym}
              type="button"
              onClick={() => {
                setBasketTouched(true);
                setBasketInput([...new Set([...activeSymbols, sym])].join(", "));
              }}
              className="portfolio-source__chip"
            >
              +{sym}
            </button>
          ))}
        </div>
        <p className="portfolio-source__hint">
          {t.portfolio.selectedCount.replace("{count}", String(activeSymbols.length))}
          {activeSymbols.length > 0 && activeSymbols.length < 2 ? t.portfolio.needTwo : ""}
        </p>
        {(summaryError || watchlistError) && (
          <p className="portfolio-notice portfolio-notice--error">{summaryError ?? watchlistError}</p>
        )}
      </section>

      <AppTabBar aria-label={t.portfolio.researchToolsAria} className="portfolio-research__tabs">
        <AppTabButton active={panel === "optimize"} onClick={() => onPanelChange("optimize")}>
          {t.portfolio.tabOptimizeShort}
        </AppTabButton>
        <AppTabButton active={panel === "backtest"} onClick={() => onPanelChange("backtest")}>
          {t.portfolio.tabBacktest}
        </AppTabButton>
        <AppTabButton active={panel === "exposure"} onClick={() => onPanelChange("exposure")}>
          {t.portfolio.tabExposureShort}
        </AppTabButton>
        <AppTabButton active={panel === "allocation"} onClick={() => onPanelChange("allocation")}>
          {t.portfolio.tabAllocationShort}
        </AppTabButton>
      </AppTabBar>

      {activeSymbols.length < 2 && (
        <p className="rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-sm text-amber-100">
          {t.portfolio.researchNeedSymbols}
        </p>
      )}

      {panel === "optimize" && (
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

      {panel === "exposure" && (
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

      {panel === "allocation" && <PortfolioAdvancedTab symbols={activeSymbols} />}

      <p className="text-xs text-zinc-600">{t.portfolio.quantHint}</p>
    </div>
  );
}
