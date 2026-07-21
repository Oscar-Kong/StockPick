"use client";

import Link from "next/link";
import type { DailyDashboardResponse } from "@/lib/types";
import { filterActiveDecisionItems, formatCurrency, mergeHoldingsWithDecisionItems } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { ActiveHoldingsDecisionTable } from "@/components/dashboard/daily-decision/ActiveHoldingsDecisionTable";
import { DailyActionQueue } from "@/components/dashboard/daily-decision/DailyActionQueue";
import { EmptyPortfolioState, PennyOpportunitiesPanel } from "@/components/dashboard/daily-decision/DailyDecisionPanels";
import { RiskAlertsPanel } from "@/components/dashboard/daily-decision/RiskAlertsPanel";
import { PortfolioPerformancePanel } from "@/components/portfolio/PortfolioPerformancePanel";
import { RobinhoodMcpStatusCard } from "@/components/portfolio/RobinhoodMcpStatusCard";
import { useState } from "react";

export interface PortfolioTodayProps {
  data: DailyDashboardResponse;
  robinhoodAuthenticated?: boolean;
  onSyncRobinhood?: () => void;
  onOpenActivity: () => void;
  performanceRefreshKey?: number;
}

export function PortfolioToday({
  data,
  robinhoodAuthenticated,
  onSyncRobinhood,
  onOpenActivity,
  performanceRefreshKey,
}: PortfolioTodayProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState<string | null>(null);
  const hasHoldings = (data.holdings.length ?? 0) > 0;
  const cashOnlySynced =
    !hasHoldings &&
    data.data_source === "robinhood_mcp" &&
    Boolean(robinhoodAuthenticated ?? data.robinhood_mcp_authenticated);
  const items = mergeHoldingsWithDecisionItems(
    data.holdings ?? [],
    filterActiveDecisionItems(data.decision?.items ?? [])
  );
  const showPennyOps =
    !data.is_demo_data && hasHoldings && (data.top_penny_opportunities.length ?? 0) > 0;

  // Not yet synced / CSV import needed — keep the focused empty state.
  if (!hasHoldings && !cashOnlySynced) {
    return (
      <div className="space-y-4">
        <EmptyPortfolioState
          robinhoodAuthenticated={robinhoodAuthenticated}
          onSyncRobinhood={onSyncRobinhood}
          cash={data.cash}
          dataSource={data.data_source}
        />
        <p className="text-center text-sm text-secondary">
          {t.portfolio.activityHint}{" "}
          <button type="button" className="text-primary hover:underline" onClick={onOpenActivity}>
            {t.portfolio.tabActivity}
          </button>
        </p>
      </div>
    );
  }

  return (
    <div className="portfolio-today portfolio-today--modern space-y-4">
      <PortfolioPerformancePanel
        hasHoldings={hasHoldings}
        cashOnly={cashOnlySynced}
        cash={data.cash}
        portfolioValue={data.portfolio_value}
        refreshKey={performanceRefreshKey}
      />

      {cashOnlySynced && (
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-950/40 px-4 py-3 text-sm text-secondary">
          <p className="font-medium text-zinc-100">{t.home.dailyEmptyRobinhoodCashTitle}</p>
          <p className="mt-1 leading-relaxed">
            {t.home.dailyEmptyRobinhoodCashBrief}
            {data.cash != null && (
              <>
                {" "}
                <span className="finance-value text-zinc-200">
                  {t.home.dailyEmptyRobinhoodCashAmount.replace("{cash}", formatCurrency(data.cash))}
                </span>
              </>
            )}
          </p>
          <div className="mt-2 text-xs">
            {t.portfolio.activityHint}{" "}
            <button type="button" className="text-primary hover:underline" onClick={onOpenActivity}>
              {t.portfolio.tabActivity}
            </button>
          </div>
          <details className="mt-2 text-xs">
            <summary className="cursor-pointer text-primary hover:underline">
              {t.portfolio.robinhoodMcpTroubleshoot}
            </summary>
            <RobinhoodMcpStatusCard
              authenticated={robinhoodAuthenticated}
              cash={data.cash}
              compact
              forceShow
            />
          </details>
        </div>
      )}

      <div className="portfolio-today__workspace">
        <aside className="portfolio-today__sidebar portfolio-today__sidebar--glass space-y-4">
          <DailyActionQueue items={items} density="sidebar" />
          {showPennyOps && <PennyOpportunitiesPanel items={data.top_penny_opportunities} />}
          <RiskAlertsPanel alerts={data.risk_alerts ?? []} />
        </aside>

        <div className="portfolio-today__main portfolio-today__main--glass space-y-4">
          <SectionCard
            title={t.home.dailyHoldingsTitle}
            subtitle={
              cashOnlySynced ? t.home.dailyEmptyRobinhoodCashTitle : t.home.dailyHoldingsSubtitle
            }
            variant="elevated"
            className="portfolio-holdings-card"
            action={
              <Link href="/scan?bucket=penny" className="text-sm font-medium text-primary hover:underline">
                {t.home.dailyPennyScan}
              </Link>
            }
          >
            {hasHoldings ? (
              <ActiveHoldingsDecisionTable
                items={items}
                expanded={expanded}
                onToggle={(sym) => setExpanded((cur) => (cur === sym ? null : sym))}
              />
            ) : (
              <p className="px-1 py-6 text-center text-sm text-secondary">
                {t.home.dailyEmptyRobinhoodCashBrief}
              </p>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
