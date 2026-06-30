"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { PrimaryButton, SecondaryButton } from "@/components/ui/buttons";
import {
  getDailyDashboard,
  getHomeRefreshStatus,
  previewRobinhoodCsv,
  refreshHomeData,
  runDailyDecisionNow,
  setBuyingPower,
} from "@/lib/api";
import { activeHomeNoticeIds, homeNoticeId, pruneDismissedNotices } from "@/lib/dismissedNotices";
import type { BrokerageCsvImportResponse, CsvPreviewResponse, DailyDashboardResponse } from "@/lib/types";
import { DismissibleNotice } from "@/components/ui/DismissibleNotice";
import { useTranslation, useTRef } from "@/lib/i18n";
import { DataFreshnessBanner } from "@/components/dashboard/daily-decision/DataFreshnessBanner";
import { DemoDataBanner } from "@/components/dashboard/daily-decision/DemoDataBanner";
import { CockpitStatusPill } from "@/components/dashboard/daily-decision/CockpitStatusPill";
import { formatDateTime } from "@/lib/datetime";
import { getCockpitStatus } from "@/lib/dailyDecisionUtils";
import { PortfolioToday } from "./PortfolioToday";
import { PortfolioResearch } from "./PortfolioResearch";
import { PortfolioActivity } from "./PortfolioActivity";
import { usePortfolioTab } from "./usePortfolioTab";

const POLL_MS = 5000;

export function PortfolioWorkspace() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const { tab, researchPanel, setTab, setResearchPanel, initialTabHint } = usePortfolioTab();
  const fileRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const legacyHandled = useRef(false);

  const [data, setData] = useState<DailyDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [savingCash, setSavingCash] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cashInput, setCashInput] = useState("");
  const [ipoSharesInput, setIpoSharesInput] = useState("");
  const [ipoListPriceInput, setIpoListPriceInput] = useState("");
  const [reservedInput, setReservedInput] = useState("");
  const [replaceImport, setReplaceImport] = useState(true);
  const [lastImport, setLastImport] = useState<BrokerageCsvImportResponse | null>(null);
  const [csvPreview, setCsvPreview] = useState<CsvPreviewResponse | null>(null);
  const [ledgerRefreshKey, setLedgerRefreshKey] = useState(0);
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
    if (legacyHandled.current || loading) return;
    if (initialTabHint === "activity") {
      legacyHandled.current = true;
      setTab("activity");
    } else if (initialTabHint === "research") {
      legacyHandled.current = true;
      setTab("research");
    }
  }, [initialTabHint, loading, setTab]);

  const activeNoticeKey = useMemo(() => {
    if (!data) return "";
    return activeHomeNoticeIds(data).join("\0");
  }, [data]);

  useEffect(() => {
    if (!data) return;
    pruneDismissedNotices(activeHomeNoticeIds(data));
  }, [activeNoticeKey, data]);

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
    const hasIpoOrder =
      ipoSharesInput.trim() !== "" &&
      ipoListPriceInput.trim() !== "" &&
      ipoShares > 0 &&
      ipoListPrice > 0;
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
    setCsvPreview(null);
    try {
      const preview = await previewRobinhoodCsv(file, replaceImport);
      setCsvPreview(preview);
      setTab("activity");
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.portfolio.csvReviewPreviewFailed);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onCsvApproved = async (result: BrokerageCsvImportResponse) => {
    setLastImport(result);
    setCsvPreview(null);
    setLedgerRefreshKey((k) => k + 1);
    await load();
  };

  const holdingSymbols = useMemo(
    () => (data?.holdings ?? []).map((h) => h.symbol),
    [data?.holdings]
  );

  const tabLabel = (id: typeof tab) => {
    if (id === "today") return t.portfolio.tabToday;
    if (id === "research") return t.portfolio.tabResearch;
    return t.portfolio.tabActivity;
  };

  const hasHoldings = (data?.holdings.length ?? 0) > 0;
  const canRun = Boolean(data && hasHoldings && !data.is_demo_data);
  const headerMeta = data
    ? (() => {
        const f = data.freshness;
        const lastUpdated =
          f?.last_decision_run_at
            ? formatDateTime(f.last_decision_run_at)
            : f?.last_price_update_at
              ? formatDateTime(f.last_price_update_at)
              : t.home.dailyNotSynced;
        return (
          <div className="portfolio-workspace__meta">
            <CockpitStatusPill status={getCockpitStatus(data)} />
            <span className="portfolio-workspace__source">{data.data_source_label}</span>
            <span className="portfolio-workspace__sync">
              {t.home.dailyLastUpdatedLabel}{" "}
              <span className="finance-value">{lastUpdated}</span>
            </span>
          </div>
        );
      })()
    : null;

  const headerActions =
    tab === "today" && data ? (
      <div className="flex flex-wrap items-center gap-2">
        <SecondaryButton onClick={() => void refreshData(true)} disabled={refreshing || running}>
          {refreshing ? t.home.dailyRefreshing : t.home.dailyRefreshNow}
        </SecondaryButton>
        <PrimaryButton onClick={() => void runNow()} disabled={running || refreshing || !canRun}>
          {running ? t.home.dailyRunning : t.home.dailyRunNow}
        </PrimaryButton>
      </div>
    ) : null;

  return (
    <PageContainer className="portfolio-workspace">
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

      <PageHeader
        title={t.portfolio.workspaceTitle}
        subtitle={t.portfolio.workspaceSubtitle}
        actions={headerActions}
      />
      {headerMeta && <div className="portfolio-workspace__meta-row">{headerMeta}</div>}

      {loading && !data ? (
        <LoadingSkeleton variant="home" />
      ) : error && !data ? (
        <ErrorState message={error} onRetry={() => void load()} />
      ) : data ? (
        <div className="portfolio-workspace__body space-y-4">
          <AppTabBar aria-label={t.portfolio.workspaceTabsAria} className="portfolio-workspace__tab-row">
            <AppTabButton active={tab === "today"} onClick={() => setTab("today")}>
              {tabLabel("today")}
            </AppTabButton>
            <AppTabButton active={tab === "research"} onClick={() => setTab("research")}>
              {tabLabel("research")}
            </AppTabButton>
            <AppTabButton active={tab === "activity"} onClick={() => setTab("activity")}>
              {tabLabel("activity")}
            </AppTabButton>
          </AppTabBar>

          {(data.portfolio_warnings?.length ?? 0) > 0 || error || data.is_demo_data ? (
            <div className="portfolio-workspace__notices space-y-2">
              {error && <ErrorState message={error} onRetry={() => void load()} />}
              {data.portfolio_warnings?.map((warning) => (
                <DismissibleNotice
                  key={warning}
                  noticeId={homeNoticeId.portfolioWarning(warning)}
                  className="rounded-xl border border-amber-500/25 bg-amber-500/8 px-4 py-3 text-sm leading-relaxed text-amber-100"
                >
                  {warning}
                </DismissibleNotice>
              ))}
              <DataFreshnessBanner data={data} />
              {data.is_demo_data && <DemoDataBanner />}
            </div>
          ) : (
            <DataFreshnessBanner data={data} />
          )}

          {tab === "today" && (
            <PortfolioToday
              data={data}
              onImportClick={() => {
                setTab("activity");
                triggerImport();
              }}
              onOpenActivity={() => setTab("activity")}
            />
          )}

          {tab === "research" && (
            <PortfolioResearch
              active
              holdingSymbols={holdingSymbols}
              panel={researchPanel}
              onPanelChange={setResearchPanel}
            />
          )}

          {tab === "activity" && (
            <PortfolioActivity
              data={data}
              cashInput={cashInput}
              onCashChange={setCashInput}
              ipoSharesInput={ipoSharesInput}
              onIpoSharesChange={setIpoSharesInput}
              ipoListPriceInput={ipoListPriceInput}
              onIpoListPriceChange={setIpoListPriceInput}
              reservedInput={reservedInput}
              onReservedChange={setReservedInput}
              replaceImport={replaceImport}
              onReplaceChange={setReplaceImport}
              onImportClick={triggerImport}
              onSaveBuyingPower={() => void saveBuyingPower()}
              savingCash={savingCash}
              importing={importing}
              lastImport={lastImport}
              csvPreview={csvPreview}
              onCsvPreviewCancel={() => setCsvPreview(null)}
              onCsvApproved={(result) => void onCsvApproved(result)}
              ledgerRefreshKey={ledgerRefreshKey}
              onLedgerChanged={() => {
                setLedgerRefreshKey((k) => k + 1);
                void load();
              }}
            />
          )}
        </div>
      ) : null}
    </PageContainer>
  );
}
