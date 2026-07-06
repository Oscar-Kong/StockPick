// Backtest panel that fetches strategy runs and parameter sweep results.
"use client";

import { fmt, useTranslation } from "@/lib/i18n";
import { getBacktest, listEntryVariants, runBacktestSweep } from "@/lib/api";
import type {
  BacktestParamOverrides,
  BacktestResult,
  BacktestSweepResponse,
  BacktestTearSheet,
  Bucket,
  EntryVariantItem,
  MultiHorizonBacktestResponse,
} from "@/lib/types";
import { useEffect, useState } from "react";

interface BacktestPanelProps {
  symbol: string | null;
  bucket?: Bucket;
  embedded?: BacktestResult | MultiHorizonBacktestResponse | null;
}

type BacktestEngine = "default" | "vectorbt";

const HORIZONS: Record<Bucket, string[]> = {
  penny: ["1y", "3y"],
  compounder: ["3y", "5y"],
};

function isMultiHorizon(data: unknown): data is MultiHorizonBacktestResponse {
  return typeof data === "object" && data !== null && "horizons" in data;
}

function TearSheetGrid({ sheet }: { sheet: BacktestTearSheet }) {
  const { t } = useTranslation();

  return (
    <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.excessVsBh}</dt>
        <dd className="font-medium">{sheet.excess_return_vs_buy_hold_pct ?? "—"}%</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.portfolio.calmar}</dt>
        <dd className="font-medium">{sheet.calmar_ratio ?? "—"}</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.profitFactor}</dt>
        <dd className="font-medium">{sheet.profit_factor ?? "—"}</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.oosSharpe}</dt>
        <dd className="font-medium">{sheet.out_of_sample_sharpe ?? "—"}</dd>
      </div>
      {sheet.entry_variant && (
        <div className="col-span-2 sm:col-span-4">
          <dt className="text-xs text-zinc-500">{t.backtest.entryRule}</dt>
          <dd className="text-xs font-medium text-[#7dff8e]">{sheet.entry_variant}</dd>
        </div>
      )}
    </dl>
  );
}

function MetricsGrid({ data }: { data: BacktestResult }) {
  const { t } = useTranslation();

  return (
    <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.strategyReturnNet}</dt>
        <dd className="font-medium">{data.total_return_pct}%</dd>
      </div>
      {data.gross_return_pct != null && data.costs_applied && (
        <div>
          <dt className="text-xs text-zinc-500">{t.backtest.grossReturn}</dt>
          <dd className="font-medium text-zinc-400">{data.gross_return_pct}%</dd>
        </div>
      )}
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.annualized}</dt>
        <dd className="font-medium">{data.annualized_return_pct ?? "—"}%</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.buyHold}</dt>
        <dd className="font-medium">{data.buy_hold_return_pct}%</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.winRate}</dt>
        <dd className="font-medium">{data.win_rate_pct}%</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.maxDrawdown}</dt>
        <dd className="font-medium">{data.max_drawdown_pct}%</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.sharpeApprox}</dt>
        <dd className="font-medium">{data.sharpe_ratio}</dd>
      </div>
      <div>
        <dt className="text-xs text-zinc-500">{t.backtest.trades}</dt>
        <dd className="font-medium">{data.trade_count}</dd>
      </div>
      {data.validation_passed != null && (
        <div>
          <dt className="text-xs text-zinc-500">{t.backtest.oosValidation}</dt>
          <dd className={data.validation_passed ? "font-medium text-emerald-600" : "font-medium text-amber-600"}>
            {data.validation_passed ? t.common.passed : t.common.failed}
          </dd>
        </div>
      )}
      {data.backtest_engine && (
        <div>
          <dt className="text-xs text-zinc-500">{t.common.engine}</dt>
          <dd className="font-medium">{data.backtest_engine}</dd>
        </div>
      )}
    </dl>
  );
}

export function BacktestPanel({ symbol, bucket = "penny", embedded }: BacktestPanelProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<BacktestResult | MultiHorizonBacktestResponse | null>(
    embedded ?? null
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(HORIZONS[bucket][0]);
  const [multiHorizon, setMultiHorizon] = useState(bucket === "compounder");
  const [engine, setEngine] = useState<BacktestEngine>("default");
  const [sweepData, setSweepData] = useState<BacktestSweepResponse | null>(null);
  const [sweepLoading, setSweepLoading] = useState(false);
  const [sweepTrials, setSweepTrials] = useState(12);
  const [sweepTopK, setSweepTopK] = useState(5);
  const [appliedOverrides, setAppliedOverrides] = useState<BacktestParamOverrides | null>(null);
  const [entryVariants, setEntryVariants] = useState<EntryVariantItem[]>([]);
  const [entryVariant, setEntryVariant] = useState("default");

  useEffect(() => {
    setHorizon(HORIZONS[bucket][0]);
    setMultiHorizon(bucket === "compounder");
    setSweepData(null);
    setAppliedOverrides(null);
    setEntryVariant("default");
    listEntryVariants(bucket)
      .then((res) => setEntryVariants(res.variants))
      .catch(() => setEntryVariants([]));
  }, [bucket]);

  const run = async (overrides?: BacktestParamOverrides | null) => {
    if (!symbol) return;
    setLoading(true);
    setError(null);
    try {
      const base = overrides === undefined ? appliedOverrides : overrides;
      const selectedOverrides: BacktestParamOverrides = {
        ...(base ?? {}),
        entry_variant: base?.entry_variant ?? entryVariant,
      };
      const res = await getBacktest(bucket, symbol, horizon, multiHorizon, engine, selectedOverrides);
      setData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.backtest.failed);
    } finally {
      setLoading(false);
    }
  };

  const runSweep = async () => {
    if (!symbol) return;
    setSweepLoading(true);
    setError(null);
    try {
      const res = await runBacktestSweep(
        bucket,
        symbol,
        {
          horizon,
          entry_variant: entryVariant,
          max_trials: sweepTrials,
          top_k: sweepTopK,
        },
        engine
      );
      setSweepData(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : t.backtest.sweepFailed);
      setSweepData(null);
    } finally {
      setSweepLoading(false);
    }
  };

  const applyBestParams = async () => {
    if (!sweepData?.best || !symbol) return;
    const nextOverrides: BacktestParamOverrides = {
      hold_days: sweepData.best.hold_days,
      stop_pct: sweepData.best.stop_pct,
      target_pct: sweepData.best.target_pct ?? undefined,
      entry_variant: sweepData.entry_variant ?? entryVariant,
    };
    setAppliedOverrides(nextOverrides);
    await run(nextOverrides);
  };

  if (!symbol && !data) return null;

  const stopPct =
    appliedOverrides?.stop_pct != null ? `${(appliedOverrides.stop_pct * 100).toFixed(1)}%` : "—";
  const targetPct =
    appliedOverrides?.target_pct == null
      ? t.common.default
      : `${(appliedOverrides.target_pct * 100).toFixed(1)}%`;

  return (
    <div className="surface-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{fmt(t.backtest.title, { bucket })}</h3>
        {symbol && !embedded && (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={entryVariant}
              onChange={(e) => setEntryVariant(e.target.value)}
              className="max-w-[200px] rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-100"
              title={t.backtest.entryRule}
            >
              {(entryVariants.length ? entryVariants : [{ id: "default", label: t.common.default }]).map(
                (v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                )
              )}
            </select>
            <select
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
              disabled={multiHorizon}
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-100"
            >
              {HORIZONS[bucket].map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
            <select
              value={engine}
              onChange={(e) => setEngine(e.target.value as BacktestEngine)}
              className="rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-100"
            >
              <option value="default">{t.common.engine}: default</option>
              <option value="vectorbt">{t.common.engine}: vectorbt</option>
            </select>
            <label className="flex items-center gap-1 text-xs text-zinc-500">
              <input
                type="checkbox"
                checked={multiHorizon}
                onChange={(e) => setMultiHorizon(e.target.checked)}
              />
              {t.backtest.allHorizons}
            </label>
            <button
              type="button"
              onClick={() => {
                void run();
              }}
              disabled={loading}
              className="btn-primary px-2 py-1 text-xs disabled:opacity-60"
            >
              {loading ? t.common.running : t.backtest.run}
            </button>
            <button
              type="button"
              onClick={runSweep}
              disabled={sweepLoading || multiHorizon}
              className="btn-ghost px-2 py-1 text-xs hover:bg-zinc-900/80 disabled:opacity-50"
              title={multiHorizon ? t.backtest.sweepSingleHorizon : undefined}
            >
              {sweepLoading ? t.backtest.sweeping : t.backtest.runSweep}
            </button>
          </div>
        )}
      </div>
      <p className="mt-1 text-xs text-zinc-500">{t.backtest.hint}</p>
      {appliedOverrides && !multiHorizon && (
        <p className="mt-1 text-xs text-blue-600 dark:text-blue-400">
          {fmt(t.backtest.customParams, {
            hold: appliedOverrides.hold_days ?? "—",
            stop: stopPct,
            target: targetPct,
          })}
        </p>
      )}
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      {data && isMultiHorizon(data) ? (
        <div className="mt-3 space-y-4">
          <p className="text-xs text-zinc-500">
            Strategy {data.strategy_version} — overall{" "}
            {data.overall_passed ? t.common.passed.toLowerCase() : t.common.failed.toLowerCase()}{" "}
            validation
          </p>
          {Object.entries(data.horizons).map(([h, result]) => (
            <div key={h} className="border-t border-zinc-100 pt-3 dark:border-zinc-800">
              <h4 className="text-xs font-semibold uppercase text-zinc-500">{h}</h4>
              <MetricsGrid data={result as BacktestResult} />
            </div>
          ))}
        </div>
      ) : data ? (
        <>
          <MetricsGrid data={data as BacktestResult} />
          {(data as BacktestResult).tear_sheet && (
            <TearSheetGrid sheet={(data as BacktestResult).tear_sheet!} />
          )}
        </>
      ) : null}
      {symbol && !embedded && (
        <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-zinc-500">{t.backtest.sweepSettings}</span>
            <label className="flex items-center gap-1 text-xs text-zinc-500">
              {t.backtest.trials}
              <input
                type="number"
                min={1}
                max={200}
                value={sweepTrials}
                onChange={(e) => setSweepTrials(Number(e.target.value) || 1)}
                className="w-16 rounded-md border border-zinc-200 px-1 py-0.5 text-xs dark:border-zinc-700"
              />
            </label>
            <label className="flex items-center gap-1 text-xs text-zinc-500">
              {t.backtest.topK}
              <input
                type="number"
                min={1}
                max={50}
                value={sweepTopK}
                onChange={(e) => setSweepTopK(Number(e.target.value) || 1)}
                className="w-16 rounded-md border border-zinc-200 px-1 py-0.5 text-xs dark:border-zinc-700"
              />
            </label>
          </div>
          {sweepData && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-zinc-500">
                Sweep {sweepData.engine} · {sweepData.horizon} · {sweepData.trials} trials
                {sweepData.entry_variant ? ` · ${sweepData.entry_variant}` : ""}
              </p>
              {sweepData.sweep_diagnostics && (
                <p
                  className={`text-xs ${
                    sweepData.sweep_diagnostics.overfit_risk === "high"
                      ? "text-amber-500"
                      : "text-zinc-500"
                  }`}
                >
                  {t.backtest.overfitRisk}: {sweepData.sweep_diagnostics.overfit_risk} · deflated Sharpe best{" "}
                  {sweepData.sweep_diagnostics.best_deflated_sharpe ?? "—"} · OOS pass rate{" "}
                  {(sweepData.sweep_diagnostics.oos_validation_pass_rate * 100).toFixed(0)}%
                </p>
              )}
              {sweepData.best && (
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-xs text-zinc-600 dark:text-zinc-400">
                    Best: {t.common.hold} {sweepData.best.hold_days}d, {t.common.stop}{" "}
                    {(sweepData.best.stop_pct * 100).toFixed(1)}%, target{" "}
                    {sweepData.best.target_pct == null
                      ? t.common.default
                      : `${(sweepData.best.target_pct * 100).toFixed(1)}%`}{" "}
                    · {t.common.return} {sweepData.best.total_return_pct.toFixed(2)}% · {t.common.sharpe}{" "}
                    {sweepData.best.sharpe_ratio.toFixed(2)}
                    {sweepData.best.deflated_sharpe != null
                      ? ` · deflated ${sweepData.best.deflated_sharpe.toFixed(2)}`
                      : ""}
                  </p>
                  <button
                    type="button"
                    onClick={applyBestParams}
                    disabled={loading || multiHorizon}
                    className="btn-primary px-2 py-0.5 text-xs disabled:opacity-50"
                    title={multiHorizon ? t.backtest.applySingleHorizon : undefined}
                  >
                    {t.backtest.applyBest}
                  </button>
                </div>
              )}
              <div className="overflow-x-auto rounded-lg border border-zinc-200/80 dark:border-zinc-800/80">
                <table className="w-full text-xs">
                  <thead className="bg-zinc-50 dark:bg-zinc-900">
                    <tr className="text-left text-zinc-500">
                      <th className="py-1">{t.backtest.colHold}</th>
                      <th className="py-1">{t.backtest.colStop}</th>
                      <th className="py-1">{t.backtest.colTarget}</th>
                      <th className="py-1">{t.backtest.colReturn}</th>
                      <th className="py-1">{t.backtest.colSharpe}</th>
                      <th className="py-1">{t.backtest.colDefl}</th>
                      <th className="py-1">{t.backtest.colDrawdown}</th>
                      <th className="py-1">{t.backtest.colTrades}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sweepData.results.map((row, idx) => (
                      <tr
                        key={`${row.hold_days}-${row.stop_pct}-${row.target_pct ?? "none"}-${idx}`}
                        className="border-t border-zinc-100 dark:border-zinc-900"
                      >
                        <td className="py-1">{row.hold_days}d</td>
                        <td className="py-1">{(row.stop_pct * 100).toFixed(1)}%</td>
                        <td className="py-1">
                          {row.target_pct == null
                            ? t.common.default
                            : `${(row.target_pct * 100).toFixed(1)}%`}
                        </td>
                        <td className="py-1">{row.total_return_pct.toFixed(2)}%</td>
                        <td className="py-1">{row.sharpe_ratio.toFixed(2)}</td>
                        <td className="py-1">
                          {row.deflated_sharpe != null ? row.deflated_sharpe.toFixed(2) : "—"}
                        </td>
                        <td className="py-1">{row.max_drawdown_pct.toFixed(2)}%</td>
                        <td className="py-1">{row.trade_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
