"use client";

import { ChartMount } from "@/components/ChartMount";
import { DarkChartTooltip, darkTooltipCursor } from "@/components/DarkChartTooltip";
import { getPortfolioPerformance } from "@/lib/api/portfolio";
import { formatCurrency, formatPercent } from "@/lib/dailyDecisionUtils";
import { parseApiError } from "@/lib/apiError";
import type { PortfolioPerformanceResponse } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type PerformanceRange = "1d" | "1w" | "1m" | "6m" | "1y";

const RANGES: PerformanceRange[] = ["1d", "1w", "1m", "6m", "1y"];

function plTone(value: number | null | undefined): "positive" | "negative" | "default" {
  if (value == null || Number.isNaN(value) || value === 0) return "default";
  return value > 0 ? "positive" : "negative";
}

function signedCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${formatCurrency(Math.abs(value))}`;
}

type PortfolioPerformancePanelProps = {
  refreshKey?: number;
  hasHoldings?: boolean;
  /** Cash-only MCP account — show buying-power hero instead of hiding. */
  cashOnly?: boolean;
  cash?: number;
  portfolioValue?: number;
};

export function PortfolioPerformancePanel({
  refreshKey = 0,
  hasHoldings = true,
  cashOnly = false,
  cash,
  portfolioValue,
}: PortfolioPerformancePanelProps) {
  const { t } = useTranslation();
  const [range, setRange] = useState<PerformanceRange>("1m");
  const [data, setData] = useState<PortfolioPerformanceResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    // Cash-only still has an equity curve (ledger + buying power) — do not skip the chart.
    if (!hasHoldings && !cashOnly) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getPortfolioPerformance());
    } catch (e) {
      setError(parseApiError(e, t.portfolio.performanceLoadFailed));
    } finally {
      setLoading(false);
    }
  }, [cashOnly, hasHoldings, t.portfolio.performanceLoadFailed]);

  useEffect(() => {
    void load();
  }, [load, refreshKey]);

  const chartData = useMemo(() => {
    const curve = data?.curves?.[range] ?? [];
    return curve.map((p) => ({
      date: p.date.length >= 10 ? p.date.slice(5) : p.date,
      fullDate: p.date,
      value: p.value,
    }));
  }, [data?.curves, range]);

  const periodPct = data?.period_change_pct?.[range] ?? null;
  const chartUp = (periodPct ?? 0) >= 0;
  const stroke = chartUp ? "var(--color-buy)" : "var(--negative)";
  const gradientId = chartUp ? "portfolioPerfUp" : "portfolioPerfDown";

  const rangeLabel = (r: PerformanceRange) => {
    if (r === "1d") return t.portfolio.performanceRange1d;
    if (r === "1w") return t.portfolio.performanceRange1w;
    if (r === "1m") return t.portfolio.performanceRange1m;
    if (r === "6m") return t.portfolio.performanceRange6m;
    return t.portfolio.performanceRange1y;
  };

  if (!hasHoldings && !cashOnly) return null;

  const displayValue =
    data?.total_value ?? (cashOnly ? (portfolioValue ?? cash ?? 0) : 0);

  return (
    <section className="portfolio-performance-hero" aria-labelledby="portfolio-performance-heading">
      <div className="portfolio-performance-hero__chart-shell">
        <div className="portfolio-performance-hero__top">
          <div className="min-w-0">
            <p id="portfolio-performance-heading" className="portfolio-performance-hero__label">
              {t.portfolio.performanceTotalValue}
            </p>
            {loading && !data ? (
              <p className="portfolio-performance-hero__value finance-value">—</p>
            ) : (
              <p className="portfolio-performance-hero__value finance-value">
                {formatCurrency(displayValue)}
              </p>
            )}
            {cashOnly && !hasHoldings && (
              <p className="mt-1 text-xs text-secondary">{t.portfolio.robinhoodLiveSyncCashOnly}</p>
            )}
            {periodPct != null && (
              <p
                className={clsx(
                  "portfolio-performance-hero__period finance-value text-sm font-medium",
                  chartUp ? "text-positive" : "text-negative",
                )}
              >
                {formatPercent(periodPct)} {rangeLabel(range)}
              </p>
            )}
          </div>

          <div className="portfolio-performance-hero__ranges" role="tablist" aria-label={t.portfolio.performanceRangeAria}>
            {RANGES.map((r) => (
              <button
                key={r}
                type="button"
                role="tab"
                aria-selected={range === r}
                className={clsx("portfolio-performance-hero__range-btn", range === r && "is-active")}
                onClick={() => setRange(r)}
              >
                {rangeLabel(r)}
              </button>
            ))}
          </div>
        </div>

        <ChartMount className="portfolio-performance-hero__chart">
          {/* Numeric height avoids Recharts ResponsiveContainer measuring width/height -1 on first paint. */}
          {chartData.length > 1 ? (
            <div className="h-full w-full min-h-[10rem]">
              <ResponsiveContainer width="100%" height={224}>
                <AreaChart data={chartData} margin={{ top: 8, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={stroke} stopOpacity={0.35} />
                      <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border-subtle)" strokeDasharray="3 3" vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    minTickGap={28}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fill: "var(--text-tertiary)", fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={52}
                    tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
                  />
                  <Tooltip content={<DarkChartTooltip />} cursor={darkTooltipCursor} />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={stroke}
                    strokeWidth={2}
                    fill={`url(#${gradientId})`}
                    dot={false}
                    activeDot={{ r: 3, strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <p className="flex h-full items-center justify-center text-sm text-secondary">
              {loading ? t.common.loading : t.portfolio.performanceChartEmpty}
            </p>
          )}
        </ChartMount>
      </div>

      {error && <p className="text-sm text-negative">{error}</p>}

      <div className="portfolio-performance-hero__kpis">
        <div className="portfolio-performance-kpi">
          <span className="portfolio-performance-kpi__label">{t.portfolio.performanceTodayPl}</span>
          <span
            className={clsx(
              "portfolio-performance-kpi__value finance-value",
              plTone(data?.today_pl) === "positive" && "text-positive",
              plTone(data?.today_pl) === "negative" && "text-negative",
            )}
          >
            {signedCurrency(data?.today_pl)}
          </span>
          {data?.today_pl_pct != null && (
            <span
              className={clsx(
                "portfolio-performance-kpi__hint finance-value",
                plTone(data.today_pl_pct) === "positive" && "text-positive",
                plTone(data.today_pl_pct) === "negative" && "text-negative",
              )}
            >
              {formatPercent(data.today_pl_pct)}
            </span>
          )}
        </div>
        <div className="portfolio-performance-kpi">
          <span className="portfolio-performance-kpi__label">{t.portfolio.performanceUnrealizedPl}</span>
          <span
            className={clsx(
              "portfolio-performance-kpi__value finance-value",
              plTone(data?.unrealized_pl) === "positive" && "text-positive",
              plTone(data?.unrealized_pl) === "negative" && "text-negative",
            )}
          >
            {signedCurrency(data?.unrealized_pl)}
          </span>
          {data?.unrealized_pl_pct != null && (
            <span
              className={clsx(
                "portfolio-performance-kpi__hint finance-value",
                plTone(data.unrealized_pl_pct) === "positive" && "text-positive",
                plTone(data.unrealized_pl_pct) === "negative" && "text-negative",
              )}
            >
              {formatPercent(data.unrealized_pl_pct)}
            </span>
          )}
        </div>
        <div className="portfolio-performance-kpi">
          <span className="portfolio-performance-kpi__label">{t.portfolio.performanceRealizedPl}</span>
          <span
            className={clsx(
              "portfolio-performance-kpi__value finance-value",
              plTone(data?.realized_pl) === "positive" && "text-positive",
              plTone(data?.realized_pl) === "negative" && "text-negative",
            )}
          >
            {signedCurrency(data?.realized_pl)}
          </span>
          {data?.realized_pl_source === "robinhood_mcp" &&
            (data.realized_pl_events ?? 0) !== 0 && (
              <span className="portfolio-performance-kpi__hint text-tertiary">
                {t.portfolio.performanceRealizedBreakdown
                  .replace("{equity}", signedCurrency(data.realized_pl_equity ?? 0))
                  .replace("{events}", signedCurrency(data.realized_pl_events ?? 0))}
              </span>
            )}
        </div>
      </div>

      {data?.disclaimer && (
        <p className="text-[11px] leading-relaxed text-tertiary">{data.disclaimer}</p>
      )}
    </section>
  );
}
