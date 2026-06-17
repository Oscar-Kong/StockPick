"use client";

import type { PortfolioPolicyBacktestResponse } from "@/lib/types";
import { formatDateRange, computeDrawdownSeries, type PortfolioSleeve } from "@/lib/portfolioUtils";
import { ChartMount } from "@/components/ChartMount";
import { DarkChartTooltip, darkTooltipCursor } from "@/components/DarkChartTooltip";
import { AsyncSection } from "@/components/AsyncSection";
import { useTranslation } from "@/lib/i18n";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  Area,
  AreaChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface PortfolioBacktestTabProps {
  symbolsCount: number;
  policy: "equal_weight" | "inverse_vol" | "top_n_momentum";
  onPolicyChange: (v: "equal_weight" | "inverse_vol" | "top_n_momentum") => void;
  rebalance: "weekly" | "monthly";
  onRebalanceChange: (v: "weekly" | "monthly") => void;
  lookback: "6mo" | "1y" | "2y" | "3y" | "5y";
  onLookbackChange: (v: "6mo" | "1y" | "2y" | "3y" | "5y") => void;
  sleeve: PortfolioSleeve;
  onSleeveChange: (v: PortfolioSleeve) => void;
  initialCapital: string;
  onInitialCapitalChange: (v: string) => void;
  institutional: boolean;
  onInstitutionalChange: (v: boolean) => void;
  loading: boolean;
  refreshing?: boolean;
  error: string | null;
  result: PortfolioPolicyBacktestResponse | null;
  onRun: () => void;
  onRetry: () => void;
}

export function PortfolioBacktestTab(props: PortfolioBacktestTabProps) {
  const { t } = useTranslation();
  const {
    symbolsCount,
    policy,
    onPolicyChange,
    rebalance,
    onRebalanceChange,
    lookback,
    onLookbackChange,
    sleeve,
    onSleeveChange,
    initialCapital,
    onInitialCapitalChange,
    institutional,
    onInstitutionalChange,
    loading,
    refreshing = false,
    error,
    result,
    onRun,
    onRetry,
  } = props;

  const equityData =
    result?.equity_curve.map((p, i) => ({
      date: p.date.slice(5),
      equity: p.equity,
      benchmark: result.benchmark_equity_curve?.[i]?.equity,
    })) ?? [];

  const drawdownSeries = result ? computeDrawdownSeries(result.equity_curve) : [];
  const drawdownData = drawdownSeries.map((p) => ({
    date: p.date.slice(5),
    drawdown: p.drawdown_pct,
  }));

  const dateRange = formatDateRange(result?.start_date, result?.end_date);
  const sectionState =
    loading && !result ? "loading" : error && !result ? "error" : result ? "ready" : "idle";

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">{t.portfolio.backtestDisclaimer}</p>

      <div className="surface-card grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-zinc-500">
          {t.portfolio.policy}
          <select
            value={policy}
            onChange={(e) => onPolicyChange(e.target.value as typeof policy)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          >
            <option value="equal_weight">{t.portfolio.polEqual}</option>
            <option value="inverse_vol">{t.portfolio.polInverseVol}</option>
            <option value="top_n_momentum">{t.portfolio.polTopN}</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          {t.portfolio.rebalance}
          <select
            value={rebalance}
            onChange={(e) => onRebalanceChange(e.target.value as typeof rebalance)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          >
            <option value="weekly">{t.portfolio.rebWeekly}</option>
            <option value="monthly">{t.portfolio.rebMonthly}</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          {t.portfolio.lookback}
          <select
            value={lookback}
            onChange={(e) => onLookbackChange(e.target.value as typeof lookback)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          >
            <option value="6mo">{t.portfolio.lb6mo}</option>
            <option value="1y">{t.portfolio.lb1y}</option>
            <option value="2y">{t.portfolio.lb2y}</option>
            <option value="3y">{t.portfolio.lb3y}</option>
            <option value="5y">{t.portfolio.lb5y}</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          {t.portfolio.sleeveLabel}
          <select
            value={sleeve}
            onChange={(e) => onSleeveChange(e.target.value as PortfolioSleeve)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          >
            <option value="penny">Penny</option>
            <option value="compounder">Compounder</option>
            <option value="custom">{t.portfolio.customBasket}</option>
          </select>
        </label>
        <label className="text-xs text-zinc-500">
          {t.portfolio.initialCapital}
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => onInitialCapitalChange(e.target.value)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
          />
        </label>
        <label className="flex items-end gap-2 text-xs text-zinc-400 pb-1.5 sm:col-span-2">
          <input
            type="checkbox"
            checked={institutional}
            onChange={(e) => onInstitutionalChange(e.target.checked)}
            className="rounded border-zinc-600"
          />
          {t.portfolio.institutional}
        </label>
      </div>

      {sleeve === "custom" && (
        <p className="text-xs text-zinc-500">{t.portfolio.customSleeveAssumptions}</p>
      )}

      <button
        type="button"
        onClick={onRun}
        disabled={loading || symbolsCount < 2}
        className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
      >
        {loading ? t.common.running : institutional ? t.portfolio.runInstitutional : t.portfolio.runPolicy}
      </button>

      <AsyncSection
        state={sectionState}
        loadingText={t.portfolio.backtestLoading}
        errorText={error}
        emptyText={t.portfolio.backtestIdle}
        onRetry={onRetry}
        preserveOnRefresh
        refreshing={refreshing}
      >
        {result && (
          <>
            <p className="text-xs text-zinc-500">{dateRange}</p>
            <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.totalReturn}</dt>
                <dd className="font-medium tabular-nums">{result.total_return_pct}%</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.annualized}</dt>
                <dd className="font-medium tabular-nums">{result.annualized_return_pct}%</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.maxDrawdown}</dt>
                <dd className="font-medium tabular-nums">{result.max_drawdown_pct}%</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.common.sharpe}</dt>
                <dd className="font-medium tabular-nums">{result.sharpe_ratio}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.vsBenchmark}</dt>
                <dd className="font-medium tabular-nums">{result.benchmark_return_pct}%</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.turnover}</dt>
                <dd className="font-medium tabular-nums">{result.turnover_pct}%</dd>
              </div>
            </dl>
            {equityData.length > 0 && (
              <ChartMount className="h-64 w-full min-w-0">
                <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
                  <LineChart data={equityData}>
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
                    <Tooltip content={<DarkChartTooltip />} cursor={darkTooltipCursor} />
                    <Legend />
                    <Line type="monotone" dataKey="equity" name="Portfolio" stroke="#00c805" dot={false} strokeWidth={2} />
                    <Line type="monotone" dataKey="benchmark" name="SPY" stroke="#6b7280" dot={false} strokeWidth={1.5} strokeDasharray="4 4" />
                  </LineChart>
                </ResponsiveContainer>
              </ChartMount>
            )}
            {drawdownData.length > 0 && (
              <div className="space-y-1">
                <h4 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  {t.portfolio.maxDrawdown}
                </h4>
                <ChartMount className="h-36 w-full min-w-0">
                  <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={120}>
                    <AreaChart data={drawdownData}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                      <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                      <YAxis tick={{ fontSize: 10 }} domain={["dataMin", 0]} />
                      <Tooltip content={<DarkChartTooltip />} cursor={darkTooltipCursor} />
                      <Area type="monotone" dataKey="drawdown" name="Drawdown %" stroke="#ef4444" fill="#ef444433" strokeWidth={1.5} />
                    </AreaChart>
                  </ResponsiveContainer>
                </ChartMount>
              </div>
            )}
            <details className="text-xs text-zinc-500">
              <summary className="cursor-pointer text-zinc-400">{t.portfolio.backtestAssumptions}</summary>
              <ul className="mt-2 list-inside list-disc space-y-1">
                <li>Benchmark: SPY</li>
                <li>Rebalance: {result.rebalance}</li>
                <li>Engine: {result.engine}</li>
                <li>Lookback: {result.lookback_period}</li>
                {result.notes.map((n) => (
                  <li key={n}>{n}</li>
                ))}
              </ul>
            </details>
          </>
        )}
      </AsyncSection>
    </div>
  );
}
