"use client";

import type { PortfolioSummaryResponse } from "@/lib/types";
import { formatFreshnessDate } from "@/lib/portfolioUtils";
import { AsyncSection, fmtPct } from "@/components/AsyncSection";
import { useTranslation } from "@/lib/i18n";

interface PortfolioOverviewTabProps {
  summary: PortfolioSummaryResponse | null;
  loading: boolean;
  refreshing?: boolean;
  error: string | null;
  onRetry: () => void;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-zinc-500">{label}</dt>
      <dd className="text-sm font-medium tabular-nums text-zinc-100">{value}</dd>
    </div>
  );
}

export function PortfolioOverviewTab({
  summary,
  loading,
  refreshing = false,
  error,
  onRetry,
}: PortfolioOverviewTabProps) {
  const { t } = useTranslation();
  const state = loading ? "loading" : error && !summary ? "error" : !summary ? "empty" : "ready";

  const allocationSegments = (summary?.positions ?? [])
    .filter((p) => (p.weight ?? 0) > 0)
    .slice(0, 12);

  return (
    <AsyncSection
      state={state}
      loadingText={t.portfolio.summaryLoading}
      errorText={error}
      emptyText={t.portfolio.summaryEmpty}
      onRetry={onRetry}
      preserveOnRefresh
      refreshing={refreshing}
      className="space-y-4"
    >
      {summary && (
        <>
          {summary.stale && (
            <p className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100">
              {t.common.staleData} — {t.portfolio.checkFreshness}
            </p>
          )}
          {summary.warnings.map((w) => (
            <p key={w} className="text-xs text-amber-300">
              {w}
            </p>
          ))}

          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 lg:grid-cols-4">
            <Metric label={t.portfolio.totalValue} value={`$${summary.total_value.toLocaleString()}`} />
            <Metric label={t.portfolio.investedValue} value={`$${summary.invested_value.toLocaleString()}`} />
            <Metric label={t.portfolio.availableCash} value={`$${summary.cash.toLocaleString()}`} />
            <Metric label={t.portfolio.cashPct} value={fmtPct(summary.cash_weight, 1)} />
            <Metric
              label={t.portfolio.todayChange}
              value={
                summary.today_change_pct != null
                  ? `${summary.today_change_pct >= 0 ? "+" : ""}${summary.today_change_pct.toFixed(2)}%`
                  : "Unavailable"
              }
            />
            <Metric
              label={t.portfolio.totalUnrealizedReturn}
              value={
                summary.total_unrealized_pl_pct != null
                  ? `${summary.total_unrealized_pl_pct >= 0 ? "+" : ""}${summary.total_unrealized_pl_pct.toFixed(1)}%`
                  : "Unavailable"
              }
            />
            <Metric label={t.portfolio.positionsCount} value={String(summary.active_holdings_count)} />
            <Metric
              label={t.portfolio.largestPosition}
              value={
                summary.largest_position
                  ? `${summary.largest_position}${summary.largest_position_weight != null ? ` (${fmtPct(summary.largest_position_weight, 1)})` : ""}`
                  : "—"
              }
            />
            <Metric label={t.portfolio.largestSector} value={summary.largest_sector ?? "—"} />
            <Metric
              label={t.portfolio.portfolioBeta}
              value={summary.portfolio_beta != null ? summary.portfolio_beta.toFixed(2) : "Unavailable"}
            />
            <Metric
              label={t.portfolio.estVol}
              value={
                summary.estimated_annual_volatility != null
                  ? fmtPct(summary.estimated_annual_volatility, 1)
                  : "Unavailable"
              }
            />
          </dl>

          {allocationSegments.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                {t.portfolio.allocation}
              </h4>
              <div className="flex h-3 w-full overflow-hidden rounded-full bg-zinc-800">
                {allocationSegments.map((p, i) => {
                  const hues = [142, 200, 260, 320, 40, 80];
                  const hue = hues[i % hues.length];
                  return (
                    <div
                      key={p.symbol}
                      title={`${p.symbol} ${p.weight != null ? fmtPct(p.weight, 1) : ""}`}
                      className="h-full min-w-[2px] transition-all"
                      style={{
                        width: `${Math.max(0.5, (p.weight ?? 0) * 100)}%`,
                        backgroundColor: `hsl(${hue} 55% 45%)`,
                      }}
                    />
                  );
                })}
                {summary.cash_weight > 0 && (
                  <div
                    title={`Cash ${fmtPct(summary.cash_weight, 1)}`}
                    className="h-full bg-zinc-600"
                    style={{ width: `${summary.cash_weight * 100}%` }}
                  />
                )}
              </div>
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-zinc-500">
                {allocationSegments.map((p) => (
                  <span key={p.symbol}>
                    {p.symbol} {p.weight != null ? fmtPct(p.weight, 0) : ""}
                  </span>
                ))}
                {summary.cash_weight > 0 && (
                  <span>Cash {fmtPct(summary.cash_weight, 0)}</span>
                )}
              </div>
            </div>
          )}

          <div className="grid gap-3 text-xs text-zinc-500 sm:grid-cols-3">
            <p>
              {t.portfolio.holdingsUpdated}: {formatFreshnessDate(summary.holdings_updated_at)}
            </p>
            <p>
              {t.portfolio.pricesThrough}: {formatFreshnessDate(summary.price_as_of ?? summary.last_price_update_at)}
            </p>
            <p>
              {t.portfolio.riskModelThrough}: {formatFreshnessDate(summary.risk_model_through)}
            </p>
          </div>

          {summary.positions.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-zinc-500">
                    <th className="py-1 pr-2">{t.common.symbol}</th>
                    <th className="py-1 pr-2">{t.portfolio.dailyShares}</th>
                    <th className="py-1 pr-2">{t.common.price}</th>
                    <th className="py-1 pr-2">{t.portfolio.dailyColMktVal}</th>
                    <th className="py-1 pr-2">{t.portfolio.dailyAvgCost}</th>
                    <th className="py-1 pr-2">P/L</th>
                    <th className="py-1 pr-2">{t.common.weight}</th>
                    <th className="py-1">{t.portfolio.dailyChange}</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.positions.map((p) => (
                    <tr key={p.symbol} className="border-t border-zinc-800">
                      <td className="py-1.5 font-medium">{p.symbol}</td>
                      <td className="py-1.5 tabular-nums">{p.shares}</td>
                      <td className="py-1.5 tabular-nums">
                        {p.price != null ? `$${p.price.toFixed(2)}` : "Unavailable"}
                      </td>
                      <td className="py-1.5 tabular-nums">
                        {p.market_value != null ? `$${p.market_value.toLocaleString()}` : "—"}
                      </td>
                      <td className="py-1.5 tabular-nums">
                        {p.avg_cost != null ? `$${p.avg_cost.toFixed(2)}` : "—"}
                      </td>
                      <td className="py-1.5 tabular-nums">
                        {p.unrealized_pl_pct != null ? `${p.unrealized_pl_pct.toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-1.5 tabular-nums">
                        {p.weight != null ? fmtPct(p.weight, 1) : "—"}
                      </td>
                      <td className="py-1.5 tabular-nums">
                        {p.daily_change_pct != null ? `${p.daily_change_pct.toFixed(2)}%` : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </AsyncSection>
  );
}
