"use client";

import Link from "next/link";
import type { DailyDashboardResponse } from "@/lib/types";
import { filterActiveDecisionItems, mergeHoldingsWithDecisionItems } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";
import { SectionCard } from "@/components/ui/AppCard";
import { ActiveHoldingsDecisionTable } from "@/components/dashboard/daily-decision/ActiveHoldingsDecisionTable";
import { DailyActionQueue } from "@/components/dashboard/daily-decision/DailyActionQueue";
import { PortfolioSummaryStrip } from "@/components/dashboard/daily-decision/DailyDecisionHero";
import { EmptyPortfolioState, PennyOpportunitiesPanel } from "@/components/dashboard/daily-decision/DailyDecisionPanels";
import { RiskAlertsPanel } from "@/components/dashboard/daily-decision/RiskAlertsPanel";
import { useState } from "react";

export interface PortfolioTodayProps {
  data: DailyDashboardResponse;
  onImportClick: () => void;
  onOpenActivity: () => void;
}

export function PortfolioToday({ data, onImportClick, onOpenActivity }: PortfolioTodayProps) {
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
        <EmptyPortfolioState onImportClick={onImportClick} />
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
    <div className="portfolio-today space-y-4">
      <PortfolioSummaryStrip data={data} />

      <DailyActionQueue items={items} />

      <div className="portfolio-today__grid grid gap-4 lg:grid-cols-12">
        <div className="portfolio-today__primary space-y-4 lg:col-span-8">
          <SectionCard
            title={t.home.dailyHoldingsTitle}
            subtitle={t.home.dailyHoldingsSubtitle}
            variant="elevated"
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
          {showPennyOps && <PennyOpportunitiesPanel items={data.top_penny_opportunities} />}
        </div>
        <aside className="portfolio-today__risk lg:col-span-4">
          <RiskAlertsPanel alerts={data.risk_alerts ?? []} />
        </aside>
      </div>
    </div>
  );
}
