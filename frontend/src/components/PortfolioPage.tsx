// Portfolio optimize + rebalance policy backtest for a basket of symbols.
"use client";

import {
  getWatchlist,
  optimizePortfolio,
  runPortfolioPolicyBacktest,
  runV2PortfolioBacktest,
} from "@/lib/api";
import type {
  PortfolioOptimizeResponse,
  PortfolioPolicyBacktestResponse,
} from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import { useCallback, useEffect, useMemo, useState } from "react";
import { AppTabBar, AppTabButton } from "./AppTabs";
import { ChartMount } from "./ChartMount";
import { DarkChartTooltip, darkTooltipCursor } from "./DarkChartTooltip";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type PanelTab = "optimize" | "policy";

function parseSymbols(raw: string): string[] {
  return [...new Set(raw.split(/[\s,]+/).map((s) => s.trim().toUpperCase()).filter(Boolean))];
}

export function PortfolioPage() {
  const { t } = useTranslation();
  const [panel, setPanel] = useState<PanelTab>("optimize");
  const [symbolInput, setSymbolInput] = useState("");
  const [watchlistSyms, setWatchlistSyms] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [objective, setObjective] = useState<
    "max_sharpe" | "min_vol" | "risk_parity" | "target_return" | "kelly"
  >("max_sharpe");
  const [lookback, setLookback] = useState<"6mo" | "1y" | "2y" | "3y" | "5y">("1y");
  const [maxWeight, setMaxWeight] = useState("0.35");
  const [cashBuffer, setCashBuffer] = useState("0.05");
  const [targetReturn, setTargetReturn] = useState("0.10");
  const [optimizeResult, setOptimizeResult] = useState<PortfolioOptimizeResponse | null>(null);

  const [policy, setPolicy] = useState<"equal_weight" | "inverse_vol" | "top_n_momentum">(
    "equal_weight"
  );
  const [rebalance, setRebalance] = useState<"weekly" | "monthly">("monthly");
  const [topN, setTopN] = useState("5");
  const [initialCapital, setInitialCapital] = useState("100000");
  const [policyResult, setPolicyResult] = useState<PortfolioPolicyBacktestResponse | null>(null);
  const [institutional, setInstitutional] = useState(false);

  useEffect(() => {
    getWatchlist()
      .then((items) => setWatchlistSyms(items.map((i) => i.symbol)))
      .catch(() => {});
  }, []);

  const symbols = useMemo(() => parseSymbols(symbolInput), [symbolInput]);

  const loadWatchlist = useCallback(() => {
    if (watchlistSyms.length) setSymbolInput(watchlistSyms.join(", "));
  }, [watchlistSyms]);

  const runOptimize = async () => {
    if (symbols.length < 2) {
      setError(t.portfolio.needTwoSymbols);
      return;
    }
    setLoading(true);
    setError(null);
    setOptimizeResult(null);
    try {
      const res = await optimizePortfolio({
        symbols,
        objective,
        lookback_period: lookback,
        max_weight: Number(maxWeight) || 0.35,
        cash_buffer: Number(cashBuffer) || 0.05,
        long_only: true,
        target_return: objective === "target_return" ? Number(targetReturn) : undefined,
        kelly_overlay: objective === "kelly",
      });
      setOptimizeResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.portfolio.optimizeFailed);
    } finally {
      setLoading(false);
    }
  };

  const runPolicy = async () => {
    if (symbols.length < 2) {
      setError(t.portfolio.needTwoSymbols);
      return;
    }
    setLoading(true);
    setError(null);
    setPolicyResult(null);
    try {
      const payload = {
        symbols,
        policy,
        rebalance,
        lookback_period: lookback,
        top_n: policy === "top_n_momentum" ? Number(topN) || 5 : undefined,
        initial_capital: Number(initialCapital) || 100_000,
        max_weight: Number(maxWeight) || 0.35,
        cash_buffer: Number(cashBuffer) || 0.05,
        institutional,
        sleeve: "medium" as const,
        use_universe_pit: institutional,
      };
      const res = institutional
        ? await runV2PortfolioBacktest(payload)
        : await runPortfolioPolicyBacktest(payload);
      setPolicyResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.portfolio.policyFailed);
    } finally {
      setLoading(false);
    }
  };

  const equityData =
    policyResult?.equity_curve.map((p) => ({
      date: p.date.slice(5),
      equity: p.equity,
    })) ?? [];

  return (
    <div className="space-y-4">
      <header className="page-toolbar">
        <div className="page-toolbar-title">
          <h1>{t.portfolio.title}</h1>
          <p className="page-toolbar-meta">{t.portfolio.subtitle}</p>
        </div>
        <AppTabBar aria-label={t.portfolio.toolsAria}>
          <AppTabButton active={panel === "optimize"} onClick={() => setPanel("optimize")}>
            {t.portfolio.tabOptimize}
          </AppTabButton>
          <AppTabButton active={panel === "policy"} onClick={() => setPanel("policy")}>
            {t.portfolio.tabPolicy}
          </AppTabButton>
        </AppTabBar>
      </header>

      <div className="surface-card space-y-3 p-4">
        <label className="text-xs font-medium text-zinc-500">{t.portfolio.symbolsLabel}</label>
        <textarea
          value={symbolInput}
          onChange={(e) => setSymbolInput(e.target.value)}
          rows={2}
          placeholder={t.portfolio.symbolsPlaceholder}
          className="w-full rounded-lg border border-zinc-700 bg-zinc-950/80 p-2 text-sm text-zinc-100"
        />
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={loadWatchlist} className="btn-ghost px-3 py-1.5 text-xs">
            {t.portfolio.useWatchlist}
          </button>
          {watchlistSyms.slice(0, 12).map((sym) => (
            <button
              key={sym}
              type="button"
              onClick={() =>
                setSymbolInput((prev) => {
                  const set = new Set(parseSymbols(prev));
                  set.add(sym);
                  return [...set].join(", ");
                })
              }
              className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400 hover:border-zinc-500"
            >
              +{sym}
            </button>
          ))}
        </div>
        <p className="text-xs text-zinc-600">
          {fmt(t.portfolio.selectedCount, { count: symbols.length })}
          {symbols.length > 0 && symbols.length < 2 ? t.portfolio.needTwo : ""}
        </p>
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {panel === "optimize" && (
        <div className="space-y-4">
          <div className="surface-card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-zinc-500">
              {t.portfolio.objective}
              <select
                value={objective}
                onChange={(e) => setObjective(e.target.value as typeof objective)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
              >
                <option value="max_sharpe">{t.portfolio.objMaxSharpe}</option>
                <option value="min_vol">{t.portfolio.objMinVol}</option>
                <option value="risk_parity">{t.portfolio.objRiskParity}</option>
                <option value="target_return">{t.portfolio.objTargetReturn}</option>
                <option value="kelly">{t.portfolio.objKelly}</option>
              </select>
            </label>
            <label className="text-xs text-zinc-500">
              {t.portfolio.lookback}
              <select
                value={lookback}
                onChange={(e) => setLookback(e.target.value as typeof lookback)}
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
              {t.portfolio.maxWeight}
              <input
                type="number"
                step="0.05"
                min="0.1"
                max="1"
                value={maxWeight}
                onChange={(e) => setMaxWeight(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t.portfolio.cashBuffer}
              <input
                type="number"
                step="0.01"
                min="0"
                max="0.5"
                value={cashBuffer}
                onChange={(e) => setCashBuffer(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            {objective === "target_return" && (
              <label className="text-xs text-zinc-500 sm:col-span-2">
                {t.portfolio.targetReturnHint}
                <input
                  type="number"
                  step="0.01"
                  value={targetReturn}
                  onChange={(e) => setTargetReturn(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
                />
              </label>
            )}
          </div>
          <button
            type="button"
            onClick={() => void runOptimize()}
            disabled={loading || symbols.length < 2}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
          >
            {loading ? t.common.running : t.portfolio.optimizeBtn}
          </button>

          {optimizeResult && (
            <div className="surface-card space-y-3 p-4">
              <p className="text-sm text-zinc-400">
                {t.portfolio.optimizer}: <span className="text-zinc-200">{optimizeResult.optimizer}</span>
                {" · "}
                {t.portfolio.objective}: {optimizeResult.objective}
              </p>
              {(optimizeResult.expected_return != null ||
                optimizeResult.expected_volatility != null) && (
                <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-3">
                  {optimizeResult.expected_return != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.expectedReturn}</dt>
                      <dd className="font-medium tabular-nums">
                        {(optimizeResult.expected_return * 100).toFixed(1)}%
                      </dd>
                    </div>
                  )}
                  {optimizeResult.expected_volatility != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.expectedVol}</dt>
                      <dd className="font-medium tabular-nums">
                        {(optimizeResult.expected_volatility * 100).toFixed(1)}%
                      </dd>
                    </div>
                  )}
                  {optimizeResult.expected_sharpe != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.common.sharpe}</dt>
                      <dd className="font-medium tabular-nums">
                        {optimizeResult.expected_sharpe.toFixed(2)}
                      </dd>
                    </div>
                  )}
                </dl>
              )}
              {optimizeResult.excluded.length > 0 && (
                <p className="text-xs text-amber-300">
                  {t.portfolio.excludedHistory} {optimizeResult.excluded.join(", ")}
                </p>
              )}
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-zinc-500">
                    <th className="py-1">{t.common.symbol}</th>
                    <th className="py-1">{t.common.weight}</th>
                  </tr>
                </thead>
                <tbody>
                  {optimizeResult.weights.map((w) => (
                    <tr key={w.symbol} className="border-t border-zinc-800">
                      <td className="py-2 font-medium text-zinc-100">{w.symbol}</td>
                      <td className="py-2 tabular-nums text-[#7dff8e]">
                        {(w.weight * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {optimizeResult.notes.length > 0 && (
                <ul className="list-inside list-disc text-xs text-zinc-500">
                  {optimizeResult.notes.map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}

      {panel === "policy" && (
        <div className="space-y-4">
          <div className="surface-card grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4">
            <label className="text-xs text-zinc-500">
              {t.portfolio.policy}
              <select
                value={policy}
                onChange={(e) => setPolicy(e.target.value as typeof policy)}
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
                onChange={(e) => setRebalance(e.target.value as typeof rebalance)}
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
                onChange={(e) => setLookback(e.target.value as typeof lookback)}
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
              {t.portfolio.initialCapital}
              <input
                type="number"
                value={initialCapital}
                onChange={(e) => setInitialCapital(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            {policy === "top_n_momentum" && (
              <label className="text-xs text-zinc-500">
                {t.portfolio.topN}
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={topN}
                  onChange={(e) => setTopN(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
                />
              </label>
            )}
            <label className="text-xs text-zinc-500">
              {t.portfolio.maxWeight}
              <input
                type="number"
                step="0.05"
                value={maxWeight}
                onChange={(e) => setMaxWeight(e.target.value)}
                className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-zinc-400 sm:col-span-2">
              <input
                type="checkbox"
                checked={institutional}
                onChange={(e) => setInstitutional(e.target.checked)}
                className="rounded border-zinc-600"
              />
              {t.portfolio.institutional}
            </label>
          </div>
          <button
            type="button"
            onClick={() => void runPolicy()}
            disabled={loading || symbols.length < 2}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
          >
            {loading
              ? t.common.running
              : institutional
                ? t.portfolio.runInstitutional
                : t.portfolio.runPolicy}
          </button>

          {policyResult && (
            <>
              <div className="surface-card space-y-3 p-4">
                {policyResult.institutional && (
                  <p className="text-xs text-[#7dff8e]">
                    {t.common.engine}: {policyResult.engine}
                    {policyResult.run_id ? ` · ${policyResult.run_id}` : ""}
                  </p>
                )}
                <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.totalReturn}</dt>
                    <dd className="font-medium tabular-nums">{policyResult.total_return_pct}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.annualized}</dt>
                    <dd className="font-medium tabular-nums">
                      {policyResult.annualized_return_pct}%
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.maxDrawdown}</dt>
                    <dd className="font-medium tabular-nums">{policyResult.max_drawdown_pct}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.common.sharpe}</dt>
                    <dd className="font-medium tabular-nums">{policyResult.sharpe_ratio}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.vsBenchmark}</dt>
                    <dd className="font-medium tabular-nums">
                      {policyResult.benchmark_return_pct}%
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.turnover}</dt>
                    <dd className="font-medium tabular-nums">{policyResult.turnover_pct}%</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.rebalances}</dt>
                    <dd className="font-medium tabular-nums">{policyResult.rebalance_count}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-zinc-500">{t.portfolio.finalCapital}</dt>
                    <dd className="font-medium tabular-nums">
                      ${policyResult.final_capital.toLocaleString()}
                    </dd>
                  </div>
                  {policyResult.sortino_ratio != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.sortino}</dt>
                      <dd className="font-medium tabular-nums">{policyResult.sortino_ratio}</dd>
                    </div>
                  )}
                  {policyResult.calmar_ratio != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.calmar}</dt>
                      <dd className="font-medium tabular-nums">{policyResult.calmar_ratio}</dd>
                    </div>
                  )}
                  {policyResult.beta != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.beta}</dt>
                      <dd className="font-medium tabular-nums">{policyResult.beta}</dd>
                    </div>
                  )}
                  {policyResult.alpha_vs_spy_pct != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.alphaVsSpy}</dt>
                      <dd className="font-medium tabular-nums">{policyResult.alpha_vs_spy_pct}%</dd>
                    </div>
                  )}
                  {policyResult.total_cost_pct != null && (
                    <div>
                      <dt className="text-xs text-zinc-500">{t.portfolio.totalCosts}</dt>
                      <dd className="font-medium tabular-nums">
                        {policyResult.total_cost_pct}% ($
                        {policyResult.total_cost_usd?.toLocaleString() ?? "—"})
                      </dd>
                    </div>
                  )}
                </dl>
                {policyResult.excluded.length > 0 && (
                  <p className="text-xs text-amber-300">
                    {t.portfolio.excluded} {policyResult.excluded.join(", ")}
                  </p>
                )}
                {policyResult.notes.length > 0 && (
                  <ul className="list-inside list-disc text-xs text-zinc-500">
                    {policyResult.notes.map((n, i) => (
                      <li key={i}>{n}</li>
                    ))}
                  </ul>
                )}
              </div>
              {equityData.length > 0 && (
                <div className="surface-card p-2">
                  <h3 className="mb-2 px-2 text-xs font-semibold uppercase text-zinc-500">
                    {t.portfolio.equityCurve}
                  </h3>
                  <ChartMount className="h-64 w-full min-w-0">
                    <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
                      <LineChart data={equityData}>
                        <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                        <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                        <YAxis tick={{ fontSize: 10 }} domain={["auto", "auto"]} />
                        <Tooltip
                          content={<DarkChartTooltip />}
                          cursor={darkTooltipCursor}
                          wrapperStyle={{ outline: "none" }}
                        />
                        <Line
                          type="monotone"
                          dataKey="equity"
                          stroke="#00c805"
                          dot={false}
                          strokeWidth={2}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </ChartMount>
                </div>
              )}
            </>
          )}
        </div>
      )}

      <p className="text-xs text-zinc-600">{t.portfolio.quantHint}</p>
    </div>
  );
}
