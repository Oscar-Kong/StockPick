// Home — Daily Decision cockpit (Robinhood portfolio).
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionCard } from "@/components/ui/AppCard";
import { PageContainer } from "@/components/ui/PageContainer";
import {
  getDailyDashboard,
  getHomeRefreshStatus,
  importRobinhoodCsv,
  refreshHomeData,
  runDailyDecisionNow,
  setBuyingPower,
} from "@/lib/api";
import { filterActiveDecisionItems, mergeHoldingsWithDecisionItems } from "@/lib/dailyDecisionUtils";
import type { BrokerageCsvImportResponse, DailyDashboardResponse } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import { ActiveHoldingsDecisionTable } from "./daily-decision/ActiveHoldingsDecisionTable";
import { DailyActionQueue } from "./daily-decision/DailyActionQueue";
import { DailyDecisionHero, PortfolioSummaryStrip } from "./daily-decision/DailyDecisionHero";
import {
  ClosedPositionsPanel,
  EmptyPortfolioState,
  PennyOpportunitiesPanel,
} from "./daily-decision/DailyDecisionPanels";
import { DataFreshnessBanner } from "./daily-decision/DataFreshnessBanner";
import { DemoDataBanner } from "./daily-decision/DemoDataBanner";
import { HomeJournalPanel } from "./HomeJournalPanel";
import { RiskAlertsPanel } from "./daily-decision/RiskAlertsPanel";

const POLL_MS = 5000;

export function DailyDecisionHome() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [data, setData] = useState<DailyDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [savingCash, setSavingCash] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [cashInput, setCashInput] = useState("");
  const [ipoSharesInput, setIpoSharesInput] = useState("");
  const [ipoListPriceInput, setIpoListPriceInput] = useState("");
  const [reservedInput, setReservedInput] = useState("");
  const [replaceImport, setReplaceImport] = useState(true);
  const [lastImport, setLastImport] = useState<BrokerageCsvImportResponse | null>(null);
  const [refreshJobId, setRefreshJobId] = useState<string | null>(null);

  const load = useCallback(async (opts?: { silent?: boolean; skipAutoRefresh?: boolean }) => {
    if (!opts?.silent) setLoading(true);
    setError(null);
    try {
      const dashboard = await getDailyDashboard(
        opts?.silent || opts?.skipAutoRefresh ? { skipAutoRefresh: true } : undefined
      );
      setData(dashboard);
      const f = dashboard.freshness;
      const inProgress = Boolean(f?.refresh_in_progress || f?.overall_status === "updating");
      if (f?.refresh_job_id) {
        setRefreshJobId(f.refresh_job_id);
      } else if (!inProgress) {
        setRefreshJobId(null);
      }
      setRefreshing(inProgress);
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyLoadFailed);
    } finally {
      if (!opts?.silent) setLoading(false);
    }
  }, [tRef]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (loading) return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("journal") === "1" || window.location.hash === "#home-journal") {
      requestAnimationFrame(() => {
        document.getElementById("home-journal")?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    }
  }, [loading, data]);

  useEffect(() => {
    if (data?.cash != null && data.cash > 0 && !cashInput.trim()) {
      setCashInput(String(data.cash));
    }
  }, [data?.cash, cashInput]);

  useEffect(() => {
    if (data?.reserved_cash != null && !reservedInput.trim() && !(data.ipo_shares && data.ipo_list_price)) {
      setReservedInput(String(data.reserved_cash));
    }
  }, [data?.reserved_cash, data?.ipo_shares, data?.ipo_list_price, reservedInput]);

  useEffect(() => {
    if (data?.ipo_shares != null && data.ipo_shares > 0 && !ipoSharesInput.trim()) {
      setIpoSharesInput(String(data.ipo_shares));
    }
  }, [data?.ipo_shares, ipoSharesInput]);

  useEffect(() => {
    if (data?.ipo_list_price != null && data.ipo_list_price > 0 && !ipoListPriceInput.trim()) {
      setIpoListPriceInput(String(data.ipo_list_price));
    }
  }, [data?.ipo_list_price, ipoListPriceInput]);

  useEffect(() => {
    if (!refreshJobId && !refreshing) {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }

    const poll = async () => {
      if (refreshJobId) {
        try {
          const status = await getHomeRefreshStatus(refreshJobId);
          if (status.status === "completed" || status.status === "failed") {
            setRefreshJobId(null);
            setRefreshing(false);
            await load({ silent: true, skipAutoRefresh: true });
          }
        } catch {
          // Job may have expired after server restart — fall back to dashboard polling.
          setRefreshJobId(null);
          await load({ silent: true, skipAutoRefresh: true });
        }
      } else if (refreshing) {
        await load({ silent: true, skipAutoRefresh: true });
      }
    };

    void poll();
    pollRef.current = setInterval(() => void poll(), POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [refreshJobId, refreshing, load]);

  const refreshData = async (force = false) => {
    setRefreshing(true);
    setError(null);
    try {
      const res = await refreshHomeData(force);
      if (res.job_id) {
        setRefreshJobId(res.job_id);
      } else if (res.status === "running") {
        // Backend refresh already in progress — poll dashboard until it clears.
        setRefreshJobId(null);
      } else if (res.status === "completed") {
        await load({ silent: true, skipAutoRefresh: true });
        setRefreshing(false);
        setRefreshJobId(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyRefreshFailed);
      setRefreshing(false);
      setRefreshJobId(null);
    }
  };

  const runNow = async () => {
    setRunning(true);
    setError(null);
    try {
      await runDailyDecisionNow();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyRunFailed);
    } finally {
      setRunning(false);
    }
  };

  const triggerImport = () => fileRef.current?.click();

  const saveBuyingPower = async () => {
    const cash = Number(cashInput);
    if (!cashInput.trim() || Number.isNaN(cash) || cash < 0) return;
    const ipoShares = Number(ipoSharesInput);
    const ipoListPrice = Number(ipoListPriceInput);
    const hasIpoOrder = ipoSharesInput.trim() !== "" && ipoListPriceInput.trim() !== "" && ipoShares > 0 && ipoListPrice > 0;
    const reserved = hasIpoOrder
      ? Math.round(ipoShares * ipoListPrice * 1.2 * 100) / 100
      : Number(reservedInput) || 0;
    setSavingCash(true);
    setError(null);
    try {
      await setBuyingPower(
        cash,
        reserved,
        hasIpoOrder ? { shares: ipoShares, listPrice: ipoListPrice } : undefined
      );
      await load({ silent: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyImportFailed);
    } finally {
      setSavingCash(false);
    }
  };

  const onImport = async (file: File) => {
    setImporting(true);
    setError(null);
    try {
      const cash = cashInput.trim() ? Number(cashInput) : undefined;
      const result = await importRobinhoodCsv(file, cash, replaceImport);
      setLastImport(result);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyImportFailed);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const hasHoldings = (data?.holdings.length ?? 0) > 0;
  const items = mergeHoldingsWithDecisionItems(
    data?.holdings ?? [],
    filterActiveDecisionItems(data?.decision?.items ?? [])
  );
  const showPennyOps =
    !data?.is_demo_data && hasHoldings && (data?.top_penny_opportunities.length ?? 0) > 0;

  const csvImportProps = {
    cashInput,
    onCashChange: setCashInput,
    ipoSharesInput,
    onIpoSharesChange: setIpoSharesInput,
    ipoListPriceInput,
    onIpoListPriceChange: setIpoListPriceInput,
    reservedInput,
    onReservedChange: setReservedInput,
    replaceImport,
    onReplaceChange: setReplaceImport,
    onImportClick: triggerImport,
    onSaveBuyingPower: () => void saveBuyingPower(),
    savingCash,
    importing,
    lastImport,
    csvRowsLoaded: data?.csv_rows_loaded,
    ledgerRowsCount: data?.ledger_rows_count,
  };

  return (
    <PageContainer className="home">
      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void onImport(f);
        }}
      />

      {loading && !data ? (
        <LoadingSkeleton variant="home" />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : data ? (
        <>
          {error && <ErrorState message={error} onRetry={() => void load()} />}
          {data.portfolio_warnings?.map((warning) => (
            <div
              key={warning}
              className="rounded-xl border border-amber-500/25 bg-amber-500/8 px-4 py-3 text-sm leading-relaxed text-amber-100"
              role="status"
            >
              {warning}
            </div>
          ))}
          <DataFreshnessBanner data={data} />
          {data.is_demo_data && <DemoDataBanner onImportClick={triggerImport} />}

          <DailyDecisionHero
            data={data}
            onRunNow={() => void runNow()}
            onRefreshData={() => void refreshData(true)}
            onImportClick={triggerImport}
            running={running}
            refreshing={refreshing}
            canRun={hasHoldings && !data.is_demo_data}
          />

          {hasHoldings && <PortfolioSummaryStrip data={data} />}

          {!hasHoldings ? (
            <>
              <EmptyPortfolioState onImportClick={triggerImport} />
              <HomeJournalPanel csvImport={csvImportProps} />
            </>
          ) : (
            <>
              <DailyActionQueue items={items} />

              <div className="grid gap-5 lg:grid-cols-12 lg:gap-6">
                <div className="space-y-5 lg:col-span-8">
                  <SectionCard
                    title={t.home.dailyHoldingsTitle}
                    subtitle={t.home.dailyHoldingsSubtitle}
                    variant="elevated"
                    action={
                      <Link href="/scan?bucket=penny" className="text-sm font-medium text-brand hover:underline">
                        {t.home.dailyPennyScan}
                      </Link>
                    }
                  >
                    <ActiveHoldingsDecisionTable
                      items={items}
                      expanded={expanded}
                      onToggle={(sym) => setExpanded((cur) => (cur === sym ? null : sym))}
                    />
                  </SectionCard>

                  {showPennyOps && <PennyOpportunitiesPanel items={data.top_penny_opportunities} />}
                  <ClosedPositionsPanel closed={data.closed_positions ?? []} />
                </div>

                <aside className="space-y-5 lg:col-span-4">
                  <RiskAlertsPanel alerts={data.risk_alerts ?? []} />
                  <HomeJournalPanel csvImport={csvImportProps} />
                </aside>
              </div>
            </>
          )}

          <p className="text-center text-sm leading-relaxed text-secondary">{data.disclaimer || t.home.dailyDisclaimer}</p>
        </>
      ) : null}
    </PageContainer>
  );
}
