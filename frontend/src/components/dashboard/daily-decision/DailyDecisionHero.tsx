import clsx from "clsx";
import { formatDateTime } from "@/lib/datetime";
import { formatCurrency, getCockpitStatus } from "@/lib/dailyDecisionUtils";
import type { DailyDashboardResponse } from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import { AppCard } from "@/components/ui/AppCard";
import { GhostButton, PrimaryButton, SecondaryButton } from "@/components/ui/buttons";
import { CurrencyText, LabelCaps } from "@/components/ui/typography";
import { MetricCard } from "@/components/ui/MetricCard";
import { CockpitStatusPill } from "./CockpitStatusPill";

interface DailyDecisionHeroProps {
  data: DailyDashboardResponse;
  onRunNow: () => void;
  onRefreshData: () => void;
  onImportClick?: () => void;
  running: boolean;
  refreshing: boolean;
  canRun: boolean;
}

export function DailyDecisionHero({
  data,
  onRunNow,
  onRefreshData,
  onImportClick,
  running,
  refreshing,
  canRun,
}: DailyDecisionHeroProps) {
  const { t } = useTranslation();
  const status = getCockpitStatus(data);
  const f = data.freshness;

  return (
    <AppCard variant="elevated" className="p-6 md:p-8" as="section">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0 flex-1 space-y-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <CockpitStatusPill status={status} />
            <span className="rounded-full border border-white/8 bg-zinc-800/80 px-2.5 py-1 text-xs text-secondary">
              {data.data_source_label}
            </span>
          </div>

          <div>
            <h1 className="page-title">{t.home.dailyHeroTitle}</h1>
            <p className="page-lead">{t.home.dailyHeroSubtitle}</p>
          </div>

          <div>
            <LabelCaps>{t.home.dailyPortfolioValue}</LabelCaps>
            <CurrencyText tone="positive" className="finance-value-xl mt-2 block">
              {formatCurrency(data.portfolio_value, { compact: true })}
            </CurrencyText>
            <p className="mt-2 text-sm text-secondary">
              {fmt(t.home.dailyPortfolioBreakdown, {
                cash: formatCurrency(data.cash, { compact: true }),
                reserved: formatCurrency(data.reserved_cash ?? 0, { compact: true }),
                invested: formatCurrency(data.invested_value ?? 0, { compact: true }),
              })}
            </p>
          </div>

          {f && (
            <p className="text-xs text-tertiary">
              {t.home.dailyLastUpdatedLabel}{" "}
              <span className="finance-value text-secondary">
                {f.last_decision_run_at
                  ? formatDateTime(f.last_decision_run_at)
                  : f.last_price_update_at
                    ? formatDateTime(f.last_price_update_at)
                    : t.home.dailyNotSynced}
              </span>
            </p>
          )}
        </div>

        <div className="flex w-full shrink-0 flex-col gap-2 sm:w-auto sm:min-w-[200px]">
          <SecondaryButton
            onClick={onRefreshData}
            disabled={refreshing || running}
            className="w-full rounded-xl"
          >
            {refreshing ? t.home.dailyRefreshing : t.home.dailyRefreshNow}
          </SecondaryButton>
          {onImportClick && (
            <GhostButton onClick={onImportClick} className="w-full rounded-xl">
              {t.home.dailyImportCsv}
            </GhostButton>
          )}
          <PrimaryButton
            onClick={onRunNow}
            disabled={running || refreshing || !canRun}
            className="w-full rounded-xl"
          >
            {running ? t.home.dailyRunning : t.home.dailyRunNow}
          </PrimaryButton>
          <p className="text-center text-xs leading-relaxed text-tertiary lg:text-right">{t.home.dailyScheduleHint}</p>
        </div>
      </div>
    </AppCard>
  );
}

export function PortfolioSummaryStrip({ data }: { data: DailyDashboardResponse }) {
  const { t } = useTranslation();
  const stats = [
    { label: t.home.dailyCash, value: formatCurrency(data.cash, { compact: true }) },
    { label: t.home.dailyReservedIpo, value: formatCurrency(data.reserved_cash ?? 0, { compact: true }) },
    { label: t.home.dailyInvested, value: formatCurrency(data.invested_value ?? 0, { compact: true }) },
    { label: t.home.dailyCashPct, value: `${(data.cash_pct ?? 0).toFixed(1)}%` },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {stats.map((s) => (
        <MetricCard key={s.label} label={s.label} value={s.value} />
      ))}
    </div>
  );
}
