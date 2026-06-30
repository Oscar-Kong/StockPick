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
import { CockpitStatusPill } from "@/components/dashboard/daily-decision/CockpitStatusPill";
import { formatDateTime } from "@/lib/datetime";
import { formatCurrency, getCockpitStatus } from "@/lib/dailyDecisionUtils";
import { CurrencyText } from "@/components/ui/typography";
import { PrimaryButton, SecondaryButton } from "@/components/ui/buttons";
import { useState } from "react";

export interface PortfolioTodayProps {
  data: DailyDashboardResponse;
  running: boolean;
  refreshing: boolean;
  onRunNow: () => void;
  onRefreshData: () => void;
  onImportClick: () => void;
  onOpenActivity: () => void;
}

export function PortfolioToday({
  data,
  running,
  refreshing,
  onRunNow,
  onRefreshData,
  onImportClick,
  onOpenActivity,
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
  const status = getCockpitStatus(data);
  const f = data.freshness;
  const lastUpdated =
    f?.last_decision_run_at
      ? formatDateTime(f.last_decision_run_at)
      : f?.last_price_update_at
        ? formatDateTime(f.last_price_update_at)
        : t.home.dailyNotSynced;
  const canRun = hasHoldings && !data.is_demo_data;

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
    <div className="space-y-4">
      <div className="portfolio-today-toolbar">
        <div className="flex flex-wrap items-center gap-2">
          <CockpitStatusPill status={status} />
          <span className="rounded-md border border-white/8 bg-zinc-800/60 px-2 py-0.5 text-sm text-secondary">
            {data.data_source_label}
          </span>
          <span className="text-sm text-secondary">
            {t.home.dailyPortfolioValue}{" "}
            <CurrencyText tone="positive" className="font-semibold">
              {formatCurrency(data.portfolio_value, { compact: true })}
            </CurrencyText>
          </span>
          <span className="text-sm text-secondary" aria-hidden>
            ·
          </span>
          <span className="text-sm text-secondary">
            {t.home.dailyLastUpdatedLabel}{" "}
            <span className="finance-value">{lastUpdated}</span>
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SecondaryButton onClick={onRefreshData} disabled={refreshing || running}>
            {refreshing ? t.home.dailyRefreshing : t.home.dailyRefreshNow}
          </SecondaryButton>
          <PrimaryButton onClick={onRunNow} disabled={running || refreshing || !canRun}>
            {running ? t.home.dailyRunning : t.home.dailyRunNow}
          </PrimaryButton>
        </div>
      </div>

      <PortfolioSummaryStrip data={data} />

      <DailyActionQueue items={items} />

      <div className="grid gap-4 lg:grid-cols-12">
        <div className="space-y-4 lg:col-span-8">
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
        <aside className="lg:col-span-4">
          <RiskAlertsPanel alerts={data.risk_alerts ?? []} />
        </aside>
      </div>
    </div>
  );
}
