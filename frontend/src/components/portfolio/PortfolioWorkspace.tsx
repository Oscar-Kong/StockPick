"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { ActionButton, SecondaryButton } from "@/components/ui/buttons";
import { activeHomeNoticeIds, homeNoticeId, pruneDismissedNotices } from "@/lib/dismissedNotices";
import { DismissibleNotice } from "@/components/ui/DismissibleNotice";
import { useTranslation } from "@/lib/i18n";
import { DataFreshnessBanner } from "@/components/dashboard/daily-decision/DataFreshnessBanner";
import { DemoDataBanner } from "@/components/dashboard/daily-decision/DemoDataBanner";
import { CockpitStatusPill } from "@/components/dashboard/daily-decision/CockpitStatusPill";
import { formatDateTime } from "@/lib/datetime";
import { getCockpitStatus } from "@/lib/dailyDecisionUtils";
import { useDailyDashboard } from "@/hooks/useDailyDashboard";
import { PortfolioToday } from "./PortfolioToday";
import { PortfolioPlan } from "./PortfolioPlan";
import { PortfolioResearch } from "./PortfolioResearch";
import { PortfolioActivity } from "./PortfolioActivity";
import { RobinhoodSyncButton } from "./RobinhoodSyncButton";
import { useRobinhoodMcpSync } from "./useRobinhoodMcpSync";
import { usePortfolioTab } from "./usePortfolioTab";

export function PortfolioWorkspace() {
  const { t } = useTranslation();
  const { tab, researchPanel, setTab, setResearchPanel, initialTabHint } = usePortfolioTab();
  const legacyHandled = useRef(false);

  const {
    data,
    loading,
    running,
    refreshing,
    error,
    load,
    refresh,
    runDecision,
  } = useDailyDashboard({
    loadFailed: t.home.dailyLoadFailed,
    refreshFailed: t.home.dailyRefreshFailed,
    runFailed: t.home.dailyRunFailed,
  });

  const [ledgerReloadToken, setLedgerReloadToken] = useState(0);

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

  const refreshData = (force = false) => void refresh(force);
  const runNow = () => void runDecision();

  const onRobinhoodSynced = useCallback(() => {
    setLedgerReloadToken((k) => k + 1);
    void load({ silent: true });
  }, [load]);
  const rhSync = useRobinhoodMcpSync(onRobinhoodSynced);

  const holdingSymbols = useMemo(
    () => (data?.holdings ?? []).map((h) => h.symbol),
    [data?.holdings]
  );

  const tabLabel = (id: typeof tab) => {
    if (id === "today") return t.portfolio.tabToday;
    if (id === "plan") return t.portfolio.tabPlan;
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

  const showRhSync =
    tab === "today" &&
    data?.robinhood_mcp_enabled !== false &&
    Boolean(data?.robinhood_mcp_authenticated);

  const headerActions =
    (tab === "today" || tab === "plan") && data ? (
      <div className="flex flex-wrap items-center gap-2">
        {showRhSync && (
          <RobinhoodSyncButton
            syncing={rhSync.syncing}
            disabled={refreshing || running}
            onSync={() => void rhSync.sync()}
          />
        )}
        <SecondaryButton onClick={() => void refreshData(true)} disabled={refreshing || running}>
          {refreshing ? t.home.dailyRefreshing : t.home.dailyRefreshNow}
        </SecondaryButton>
        <ActionButton onClick={() => void runNow()} disabled={running || refreshing || !canRun}>
          {running ? t.home.dailyRunning : t.home.dailyRunNow}
        </ActionButton>
      </div>
    ) : null;

  return (
    <PageContainer className="portfolio-workspace portfolio-workspace--modern">
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
            <AppTabButton active={tab === "plan"} onClick={() => setTab("plan")}>
              {tabLabel("plan")}
            </AppTabButton>
            <AppTabButton active={tab === "activity"} onClick={() => setTab("activity")}>
              {tabLabel("activity")}
            </AppTabButton>
            <AppTabButton active={tab === "research"} onClick={() => setTab("research")}>
              {tabLabel("research")}
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

          {(tab === "today" || tab === "activity") && (rhSync.message || rhSync.error) && (
            <p
              className={
                rhSync.error
                  ? "text-sm text-negative"
                  : "text-sm text-secondary"
              }
            >
              {rhSync.error ?? rhSync.message}
            </p>
          )}

          {tab === "today" && (
            <PortfolioToday
              data={data}
              robinhoodAuthenticated={Boolean(data.robinhood_mcp_authenticated)}
              onSyncRobinhood={
                data.robinhood_mcp_authenticated ? () => void rhSync.sync() : undefined
              }
              onOpenActivity={() => setTab("activity")}
              performanceRefreshKey={ledgerReloadToken}
            />
          )}

          {tab === "plan" && <PortfolioPlan data={data} />}

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
              reloadToken={ledgerReloadToken}
              onSyncRobinhood={() => void rhSync.sync()}
              syncingRobinhood={rhSync.syncing}
              syncDisabled={refreshing || running}
              syncMessage={rhSync.message}
              syncError={rhSync.error}
            />
          )}
        </div>
      ) : null}
    </PageContainer>
  );
}
