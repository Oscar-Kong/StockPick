import clsx from "clsx";
import { formatDateTime } from "@/lib/datetime";
import { formatCurrency, getCockpitStatus } from "@/lib/dailyDecisionUtils";
import type { DailyDashboardResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { GhostButton, PrimaryButton, SecondaryButton } from "@/components/ui/buttons";
import { CurrencyText } from "@/components/ui/typography";
import { SummaryStrip, SummaryStripItem } from "@/components/ui/SummaryStrip";
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
  const lastUpdated =
    f?.last_decision_run_at
      ? formatDateTime(f.last_decision_run_at)
      : f?.last_price_update_at
        ? formatDateTime(f.last_price_update_at)
        : t.home.dailyNotSynced;

  return (
    <header className="home-compact-header">
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="home-compact-header__title">{t.home.dailyHeroTitle}</h1>
          <CockpitStatusPill status={status} />
          <span className="rounded-md border border-white/8 bg-zinc-800/60 px-2 py-0.5 text-sm text-secondary">
            {data.data_source_label}
          </span>
        </div>
        <div className="home-compact-header__meta">
          <span>
            {t.home.dailyPortfolioValue}{" "}
            <CurrencyText tone="positive" className="text-base font-semibold">
              {formatCurrency(data.portfolio_value, { compact: true })}
            </CurrencyText>
          </span>
          <span aria-hidden>·</span>
          <span>
            {t.home.dailyLastUpdatedLabel}{" "}
            <span className="finance-value text-secondary">{lastUpdated}</span>
          </span>
        </div>
      </div>

      <div className="flex w-full shrink-0 flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
        <SecondaryButton onClick={onRefreshData} disabled={refreshing || running}>
          {refreshing ? t.home.dailyRefreshing : t.home.dailyRefreshNow}
        </SecondaryButton>
        {onImportClick && (
          <GhostButton onClick={onImportClick}>{t.home.dailyImportCsv}</GhostButton>
        )}
        <PrimaryButton onClick={onRunNow} disabled={running || refreshing || !canRun}>
          {running ? t.home.dailyRunning : t.home.dailyRunNow}
        </PrimaryButton>
      </div>
    </header>
  );
}

export function PortfolioSummaryStrip({ data }: { data: DailyDashboardResponse }) {
  const { t } = useTranslation();

  return (
    <SummaryStrip>
      <SummaryStripItem label={t.home.dailyCash} value={formatCurrency(data.cash, { compact: true })} />
      <SummaryStripItem
        label={t.home.dailyReservedIpo}
        value={formatCurrency(data.reserved_cash ?? 0, { compact: true })}
      />
      <SummaryStripItem
        label={t.home.dailyInvested}
        value={formatCurrency(data.invested_value ?? 0, { compact: true })}
        tone="positive"
      />
      <SummaryStripItem
        label={t.home.dailyCashPct}
        value={`${(data.cash_pct ?? 0).toFixed(1)}%`}
        className={clsx((data.cash_pct ?? 0) > 40 && "summary-strip__item--warn")}
      />
    </SummaryStrip>
  );
}
