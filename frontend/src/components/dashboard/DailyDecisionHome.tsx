// Home — Daily Decision cockpit for Robinhood holdings.
"use client";

import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getDailyDashboard, importRobinhoodCsv, runDailyDecisionNow } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import type { DailyDashboardResponse, PortfolioDecisionItem } from "@/lib/types";
import { fmt, useTranslation, useTRef } from "@/lib/i18n";
import Link from "next/link";
import { Fragment, useCallback, useEffect, useRef, useState } from "react";

function DecisionBadge({ decision }: { decision: string }) {
  const colors: Record<string, string> = {
    buy: "text-[#7dff8e] border-[#7dff8e]/40 bg-[#7dff8e]/10",
    keep: "text-zinc-200 border-zinc-600 bg-zinc-800/60",
    sell: "text-red-300 border-red-500/40 bg-red-500/10",
    review: "text-amber-300 border-amber-500/40 bg-amber-500/10",
  };
  return (
    <span
      className={`inline-block rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase ${colors[decision] ?? colors.keep}`}
    >
      {decision}
    </span>
  );
}

function WhyPanel({ item }: { item: PortfolioDecisionItem }) {
  const { t } = useTranslation();
  const debugRows: [string, string | number | boolean | null | undefined][] = [
    [t.home.dailyDebugAlpha, item.alpha_score],
    [t.home.dailyDebugMomentum, item.momentum_score],
    [t.home.dailyDebugLiquidity, item.liquidity_score],
    [t.home.dailyDebugRisk, item.risk_score],
    [t.home.dailyDebugDq, item.data_quality_score],
    [t.home.dailyDebugMaxWt, item.max_allowed_weight != null ? `${item.max_allowed_weight}%` : "—"],
    [t.home.dailyDebugOwPenalty, item.overweight_penalty],
    [t.home.dailyDebugMissingPenalty, item.missing_data_penalty],
    [t.home.dailyDebugStopLoss, item.stop_loss_trigger ? t.common.yes : t.common.no],
    [t.home.dailyDebugBuyRaw, item.final_buy_raw],
    [t.home.dailyDebugKeepRaw, item.final_keep_raw],
    [t.home.dailyDebugSellRaw, item.final_sell_raw],
  ];

  return (
    <div className="space-y-2 rounded border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-400">
      {item.suggested_action && (
        <p className="font-medium text-zinc-300">{item.suggested_action}</p>
      )}
      {item.reasons.length > 0 && (
        <ul className="list-inside list-disc text-zinc-400">
          {item.reasons.map((r) => (
            <li key={r}>{r}</li>
          ))}
        </ul>
      )}
      {item.risk_flags.length > 0 && (
        <p className="text-amber-400/90">{item.risk_flags.join("; ")}</p>
      )}
      <p className="text-[10px] uppercase tracking-wide text-zinc-500">{t.home.dailyWhyTitle}</p>
      <div className="grid gap-1 sm:grid-cols-2 lg:grid-cols-3">
        {debugRows.map(([label, val]) => (
          <div key={label} className="flex justify-between gap-2 border-b border-zinc-900 py-0.5">
            <span>{label}</span>
            <span className="tabular-nums text-zinc-300">{val ?? "—"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DailyDecisionHome() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const fileRef = useRef<HTMLInputElement>(null);
  const [data, setData] = useState<DailyDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [cashInput, setCashInput] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getDailyDashboard());
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyLoadFailed);
    } finally {
      setLoading(false);
    }
  }, [tRef]);

  useEffect(() => {
    void load();
  }, [load]);

  const runNow = async () => {
    setRunning(true);
    setError(null);
    try {
      await runDailyDecisionNow();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyRunFailed);
    } finally {
      setRunning(false);
    }
  };

  const onImport = async (file: File) => {
    setImporting(true);
    setError(null);
    try {
      const cash = cashInput.trim() ? Number(cashInput) : undefined;
      await importRobinhoodCsv(file, cash);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.dailyImportFailed);
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const items = data?.decision?.items ?? [];
  const closed = data?.closed_positions ?? [];
  const riskAlerts = data?.risk_alerts ?? [];

  return (
    <div className="home space-y-4">
      <header className="home-hero surface-card p-4">
        <p className="home-hero-badge">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-[#00c805]" />
          {t.home.dailyBadge}
        </p>
        <h1>{t.home.dailyTitle}</h1>
        <p className="home-lead">{t.home.dailyLead}</p>
        <p className="mt-2 text-xs text-amber-400/90">{data?.disclaimer ?? t.home.dailyDisclaimer}</p>
        {data?.is_demo_data && (
          <p className="mt-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-xs text-red-300">
            {t.home.dailyDemoWarning}
          </p>
        )}
      </header>

      {loading && <LoadingSkeleton lines={6} />}
      {error && !loading && <ErrorState message={error} onRetry={() => void load()} />}

      {!loading && data && (
        <>
          {/* A. Daily Decision Summary */}
          <section className="surface-card p-4">
            <SectionHeader title={t.home.dailySummaryTitle} />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyPortfolioValue}</p>
                <p className="text-xl font-semibold tabular-nums text-[#7dff8e]">
                  ${data.portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyCash}</p>
                <p className="text-xl font-semibold tabular-nums">${data.cash.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyInvested}</p>
                <p className="text-xl font-semibold tabular-nums">
                  ${(data.invested_value ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyCashPct}</p>
                <p className="text-xl font-semibold tabular-nums">{(data.cash_pct ?? 0).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyActiveHoldings}</p>
                <p className="text-xl font-semibold tabular-nums">{data.active_holdings_count ?? data.holdings.length}</p>
              </div>
              <div>
                <p className="text-[10px] uppercase text-zinc-500">{t.home.dailyDataSource}</p>
                <p className="text-sm font-medium text-zinc-200">{data.data_source_label}</p>
                <p className="mt-0.5 text-xs text-zinc-500">
                  {data.last_brokerage_sync_at
                    ? fmt(t.home.dailySyncedAt, { time: formatDateTime(data.last_brokerage_sync_at) })
                    : t.home.dailyNotSynced}
                </p>
                <p className="text-xs text-zinc-500">
                  {data.last_decision_run_at
                    ? fmt(t.home.dailyLastRunAt, { time: formatDateTime(data.last_decision_run_at) })
                    : t.home.dailyNeverRun}
                </p>
              </div>
            </div>
          </section>

          {data.portfolio_warnings.length > 0 && (
            <ul className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200">
              {data.portfolio_warnings.map((w) => (
                <li key={w}>• {w}</li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void runNow()}
              disabled={running || !data.holdings.length}
              className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
            >
              {running ? t.home.dailyRunning : t.home.dailyRunNow}
            </button>
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              disabled={importing}
              className="btn-ghost px-4 py-2 text-sm"
            >
              {importing ? t.common.running : t.home.dailyImportCsv}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void onImport(f);
              }}
            />
            <label className="flex items-center gap-2 text-xs text-zinc-500">
              {t.home.dailyCashOnImport}
              <input
                type="number"
                min={0}
                value={cashInput}
                onChange={(e) => setCashInput(e.target.value)}
                className="w-24 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
                placeholder="auto"
              />
            </label>
            <Link href="/scan?bucket=penny" className="btn-ghost px-4 py-2 text-sm">
              {t.home.dailyPennyScan}
            </Link>
          </div>

          {/* C. Risk Alerts */}
          {riskAlerts.length > 0 && (
            <section className="surface-card border-l-2 border-l-amber-500/60 p-4">
              <SectionHeader title={t.home.dailyRiskAlertsTitle} />
              <ul className="space-y-1 text-xs text-amber-200/90">
                {riskAlerts.map((a) => (
                  <li key={a}>• {a}</li>
                ))}
              </ul>
            </section>
          )}

          {/* B. Active Holdings Decision Table */}
          <section className="surface-card p-4">
            <SectionHeader title={t.home.dailyHoldingsTitle} subtitle={t.home.dailyHoldingsSubtitle} />
            {!items.length ? (
              <p className="text-sm text-zinc-500">{t.home.dailyNoDecision}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1200px] text-left text-xs">
                  <thead className="border-b border-zinc-800 text-zinc-500">
                    <tr>
                      <th className="p-2">{t.portfolio.dailyColSymbol}</th>
                      <th className="p-2">{t.home.dailyColShares}</th>
                      <th className="p-2">{t.home.dailyColAvgCost}</th>
                      <th className="p-2">{t.home.dailyColPrice}</th>
                      <th className="p-2">{t.home.dailyColMv}</th>
                      <th className="p-2">{t.home.dailyColPl}</th>
                      <th className="p-2">{t.portfolio.dailyColCurWt}</th>
                      <th className="p-2">{t.portfolio.dailyColTgtWt}</th>
                      <th className="p-2">{t.portfolio.dailyColBuy}</th>
                      <th className="p-2">{t.portfolio.dailyColKeep}</th>
                      <th className="p-2">{t.portfolio.dailyColSell}</th>
                      <th className="p-2">{t.portfolio.dailyColDecision}</th>
                      <th className="p-2">{t.portfolio.dailyColAction}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {items.map((item) => (
                      <Fragment key={item.symbol}>
                        <tr
                          className="cursor-pointer border-b border-zinc-900 hover:bg-zinc-900/40"
                          onClick={() => setExpanded((e) => (e === item.symbol ? null : item.symbol))}
                        >
                          <td className="p-2 font-medium">
                            <Link
                              href={`/workspace?symbol=${item.symbol}`}
                              className="text-[#7dff8e] hover:underline"
                              onClick={(ev) => ev.stopPropagation()}
                            >
                              {item.symbol}
                            </Link>
                            <span className="ml-1 text-[10px] capitalize text-zinc-500">{item.bucket}</span>
                          </td>
                          <td className="p-2 tabular-nums">{item.shares.toLocaleString()}</td>
                          <td className="p-2 tabular-nums">${item.avg_cost.toFixed(2)}</td>
                          <td className="p-2 tabular-nums">
                            {item.price_available === false ? (
                              <span className="text-amber-400">—</span>
                            ) : (
                              `$${item.price.toFixed(2)}`
                            )}
                          </td>
                          <td className="p-2 tabular-nums">${item.market_value.toLocaleString()}</td>
                          <td
                            className={`p-2 tabular-nums ${(item.pl_pct ?? 0) >= 0 ? "text-[#7dff8e]" : "text-red-300"}`}
                          >
                            {item.pl_pct != null ? `${item.pl_pct >= 0 ? "+" : ""}${item.pl_pct.toFixed(1)}%` : "—"}
                          </td>
                          <td className="p-2 tabular-nums">{item.current_weight}%</td>
                          <td className="p-2 tabular-nums">{item.target_weight}%</td>
                          <td className="p-2 tabular-nums">{item.buy_pct}%</td>
                          <td className="p-2 tabular-nums">{item.keep_pct}%</td>
                          <td className="p-2 tabular-nums">{item.sell_pct}%</td>
                          <td className="p-2">
                            <DecisionBadge decision={item.decision} />
                          </td>
                          <td className="p-2 max-w-[180px] truncate text-zinc-400" title={item.suggested_action}>
                            {item.suggested_action || (
                              <>
                                {item.suggested_dollar_action >= 0 ? "+" : ""}$
                                {item.suggested_dollar_action.toLocaleString()}
                              </>
                            )}
                          </td>
                        </tr>
                        {expanded === item.symbol && (
                          <tr>
                            <td colSpan={13} className="p-2">
                              <WhyPanel item={item} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          {/* D. Top Penny Opportunities */}
          {data.top_penny_opportunities.length > 0 && (
            <section className="surface-card p-4">
              <SectionHeader
                title={t.home.dailyPennyOpsTitle}
                subtitle={t.home.dailyPennyOpsSubtitle}
                action={
                  <Link href="/scan?bucket=penny" className="text-xs text-[#7dff8e] hover:underline">
                    {t.home.openScan}
                  </Link>
                }
              />
              <ul className="divide-y divide-zinc-900 text-sm">
                {data.top_penny_opportunities.map((p) => (
                  <li key={p.symbol} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <Link href={`/workspace?symbol=${p.symbol}`} className="font-medium text-[#7dff8e]">
                      {p.symbol}
                    </Link>
                    <span className="tabular-nums text-zinc-400">
                      {p.score.toFixed(0)} · ${p.price.toFixed(2)}
                      {p.setup_type ? ` · ${p.setup_type}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* E. Closed Positions */}
          {closed.length > 0 && (
            <section className="surface-card p-4">
              <SectionHeader title={t.home.dailyClosedTitle} subtitle={t.home.dailyClosedSubtitle} />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-zinc-800 text-zinc-500">
                    <tr>
                      <th className="p-2">{t.portfolio.dailyColSymbol}</th>
                      <th className="p-2">{t.home.dailyColBought}</th>
                      <th className="p-2">{t.home.dailyColSold}</th>
                      <th className="p-2">{t.home.dailyColRealizedPl}</th>
                      <th className="p-2">{t.home.dailyColLastActivity}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {closed.map((c) => (
                      <tr key={c.symbol} className="border-b border-zinc-900 text-zinc-400">
                        <td className="p-2 font-medium text-zinc-300">{c.symbol}</td>
                        <td className="p-2 tabular-nums">{c.total_bought}</td>
                        <td className="p-2 tabular-nums">{c.total_sold}</td>
                        <td
                          className={`p-2 tabular-nums ${c.realized_pl >= 0 ? "text-[#7dff8e]" : "text-red-300"}`}
                        >
                          ${c.realized_pl.toFixed(2)}
                        </td>
                        <td className="p-2">{c.last_activity || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
