"use client";

import Link from "next/link";
import type { DailyDashboardResponse } from "@/lib/types";
import { filterActiveDecisionItems, mergeHoldingsWithDecisionItems } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { ActiveHoldingsDecisionTable } from "@/components/dashboard/daily-decision/ActiveHoldingsDecisionTable";
import { DailyActionQueue } from "@/components/dashboard/daily-decision/DailyActionQueue";
import { EmptyPortfolioState, PennyOpportunitiesPanel } from "@/components/dashboard/daily-decision/DailyDecisionPanels";
import { RiskAlertsPanel } from "@/components/dashboard/daily-decision/RiskAlertsPanel";
import { PortfolioPerformancePanel } from "@/components/portfolio/PortfolioPerformancePanel";
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
  const items = mergeHoldingsWithDecisionItems(
    data.holdings ?? [],
    filterActiveDecisionItems(data.decision?.items ?? [])
  );
  const showPennyOps =
    !data.is_demo_data && hasHoldings && (data.top_penny_opportunities.length ?? 0) > 0;

  if (!hasHoldings) {
    return (
      <div className="space-y-4">
        <EmptyPortfolioState
          robinhoodAuthenticated={robinhoodAuthenticated}
          onSyncRobinhood={onSyncRobinhood}
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
      <PortfolioPerformancePanel hasHoldings={hasHoldings} refreshKey={performanceRefreshKey} />

      <div className="portfolio-today__workspace">
        <aside className="portfolio-today__sidebar portfolio-today__sidebar--glass space-y-4">
          <DailyActionQueue items={items} density="sidebar" />
          {showPennyOps && <PennyOpportunitiesPanel items={data.top_penny_opportunities} />}
          <RiskAlertsPanel alerts={data.risk_alerts ?? []} />
        </aside>

        <div className="portfolio-today__main portfolio-today__main--glass space-y-4">
          <SectionCard
            title={t.home.dailyHoldingsTitle}
            subtitle={t.home.dailyHoldingsSubtitle}
            variant="elevated"
            className="portfolio-holdings-card"
            action={
              <Link href="/scan?bucket=penny" className="text-sm font-medium text-primary hover:underline">
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
        </div>
      </div>
    </div>
  );
}
