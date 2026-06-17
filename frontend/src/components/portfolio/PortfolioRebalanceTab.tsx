"use client";

import type {
  PortfolioOptimizeResponse,
  PortfolioSummaryResponse,
  RebalancePreviewResponse,
} from "@/lib/types";
import { checkOptimizationFeasibility } from "@/lib/portfolioUtils";
import { AsyncSection } from "@/components/AsyncSection";
import { useTranslation } from "@/lib/i18n";

type Objective = "max_sharpe" | "min_vol" | "risk_parity" | "target_return" | "kelly";

interface PortfolioRebalanceTabProps {
  symbols: string[];
  summary: PortfolioSummaryResponse | null;
  objective: Objective;
  onObjectiveChange: (v: Objective) => void;
  lookback: "6mo" | "1y" | "2y" | "3y" | "5y";
  onLookbackChange: (v: "6mo" | "1y" | "2y" | "3y" | "5y") => void;
  maxWeight: string;
  onMaxWeightChange: (v: string) => void;
  cashBuffer: string;
  onCashBufferChange: (v: string) => void;
  targetReturn: string;
  onTargetReturnChange: (v: string) => void;
  minTrade: string;
  onMinTradeChange: (v: string) => void;
  fractionalShares: boolean;
  onFractionalSharesChange: (v: boolean) => void;
  optimizeLoading: boolean;
  optimizeError: string | null;
  optimizeResult: PortfolioOptimizeResponse | null;
  onRunOptimize: () => void;
  rebalanceLoading: boolean;
  rebalanceError: string | null;
  rebalanceResult: RebalancePreviewResponse | null;
  onRunRebalance: () => void;
}

export function PortfolioRebalanceTab({
  symbols,
  summary,
  objective,
  onObjectiveChange,
  lookback,
  onLookbackChange,
  maxWeight,
  onMaxWeightChange,
  cashBuffer,
  onCashBufferChange,
  targetReturn,
  onTargetReturnChange,
  minTrade,
  onMinTradeChange,
  fractionalShares,
  onFractionalSharesChange,
  optimizeLoading,
  optimizeError,
  optimizeResult,
  onRunOptimize,
  rebalanceLoading,
  rebalanceError,
  rebalanceResult,
  onRunRebalance,
}: PortfolioRebalanceTabProps) {
  const { t } = useTranslation();
  const mw = Number(maxWeight) || 0.35;
  const cb = Number(cashBuffer) || 0.05;
  const feasibility = checkOptimizationFeasibility(symbols.length, mw, cb);

  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">{t.portfolio.rebalanceDisclaimer}</p>

      <div className="surface-card grid gap-3 p-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-xs text-zinc-500">
          {t.portfolio.objective}
          <select
            value={objective}
            onChange={(e) => onObjectiveChange(e.target.value as Objective)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm"
          >
            <option value="max_sharpe">{t.portfolio.objMaxSharpe}</option>
            <option value="min_vol">{t.portfolio.objMinVol}</option>
            <option value="risk_parity">{t.portfolio.objRiskParity}</option>
            <option value="target_return">{t.portfolio.objTargetReturn}</option>
            <option value="kelly">{t.portfolio.objKellyExperimental}</option>
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
          {t.portfolio.maxWeight}
          <input
            type="number"
            step="0.05"
            min="0.1"
            max="1"
            value={maxWeight}
            onChange={(e) => onMaxWeightChange(e.target.value)}
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
            onChange={(e) => onCashBufferChange(e.target.value)}
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
              onChange={(e) => onTargetReturnChange(e.target.value)}
              className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
            />
          </label>
        )}
        <label className="text-xs text-zinc-500">
          {t.portfolio.minTrade}
          <input
            type="number"
            min="0"
            value={minTrade}
            onChange={(e) => onMinTradeChange(e.target.value)}
            className="mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1.5 text-sm tabular-nums"
          />
        </label>
        <label className="flex items-end gap-2 text-xs text-zinc-400 pb-1.5">
          <input
            type="checkbox"
            checked={fractionalShares}
            onChange={(e) => onFractionalSharesChange(e.target.checked)}
            className="rounded border-zinc-600"
          />
          {t.portfolio.fractionalShares}
        </label>
      </div>

      <div
        className={`rounded-lg border px-3 py-2 text-xs ${
          feasibility.feasible
            ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-100"
            : "border-red-500/30 bg-red-500/10 text-red-100"
        }`}
      >
        {feasibility.feasible ? (
          <>
            {symbols.length} assets × {(mw * 100).toFixed(0)}% max = {feasibility.capacityPct.toFixed(0)}% capacity ·{" "}
            {t.portfolio.constraintFeasible}
          </>
        ) : (
          feasibility.reason
        )}
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onRunOptimize}
          disabled={optimizeLoading || !feasibility.feasible || symbols.length < 2}
          className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
        >
          {optimizeLoading ? t.common.running : t.portfolio.optimizeBtn}
        </button>
        <button
          type="button"
          onClick={onRunRebalance}
          disabled={rebalanceLoading || !optimizeResult || !summary}
          className="btn-ghost px-4 py-2 text-sm disabled:opacity-50"
        >
          {rebalanceLoading ? t.common.running : t.portfolio.previewTrades}
        </button>
      </div>

      {optimizeError && <p className="text-sm text-red-400">{optimizeError}</p>}
      {rebalanceError && <p className="text-sm text-red-400">{rebalanceError}</p>}

      {optimizeResult && (
        <div className="surface-card space-y-2 p-3 text-sm">
          <p className="text-xs text-zinc-500">
            {t.portfolio.optimizer}: {optimizeResult.optimizer} · {optimizeResult.expected_sharpe != null && `Sharpe ${optimizeResult.expected_sharpe.toFixed(2)}`}
          </p>
          {optimizeResult.excluded.length > 0 && (
            <p className="text-xs text-amber-300">
              {t.portfolio.excludedHistory} {optimizeResult.excluded.join(", ")}
            </p>
          )}
        </div>
      )}

      <AsyncSection
        state={
          rebalanceLoading && !rebalanceResult
            ? "loading"
            : rebalanceError && !rebalanceResult
              ? "error"
              : rebalanceResult
                ? "ready"
                : "idle"
        }
        loadingText={t.portfolio.rebalanceLoading}
        errorText={rebalanceError}
        emptyText={t.portfolio.rebalanceIdle}
        preserveOnRefresh
        refreshing={rebalanceLoading && !!rebalanceResult}
      >
        {rebalanceResult && (
          <div className="space-y-3">
            <dl className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.turnover}</dt>
                <dd className="font-medium tabular-nums">{(rebalanceResult.turnover_pct * 100).toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.estFees}</dt>
                <dd className="font-medium tabular-nums">${rebalanceResult.estimated_fees.toFixed(2)}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.cashAfter}</dt>
                <dd className="font-medium tabular-nums">${rebalanceResult.cash_after.toLocaleString()}</dd>
              </div>
              <div>
                <dt className="text-xs text-zinc-500">{t.portfolio.tradeCount}</dt>
                <dd className="font-medium tabular-nums">{rebalanceResult.trade_count}</dd>
              </div>
            </dl>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-zinc-500">
                    <th className="py-1">{t.common.symbol}</th>
                    <th className="py-1">{t.portfolio.curShares}</th>
                    <th className="py-1">{t.common.price}</th>
                    <th className="py-1">{t.portfolio.curValue}</th>
                    <th className="py-1">{t.portfolio.curWt}</th>
                    <th className="py-1">{t.portfolio.tgtWt}</th>
                    <th className="py-1">{t.portfolio.dollarTrade}</th>
                    <th className="py-1">{t.portfolio.shareTrade}</th>
                    <th className="py-1">{t.common.action}</th>
                  </tr>
                </thead>
                <tbody>
                  {rebalanceResult.trades.map((tr) => (
                    <tr key={tr.symbol} className="border-t border-zinc-800">
                      <td className="py-1.5 font-medium">{tr.symbol}</td>
                      <td className="py-1.5 tabular-nums">{tr.current_shares}</td>
                      <td className="py-1.5 tabular-nums">${tr.current_price.toFixed(2)}</td>
                      <td className="py-1.5 tabular-nums">${tr.current_value.toLocaleString()}</td>
                      <td className="py-1.5 tabular-nums">{(tr.current_weight * 100).toFixed(1)}%</td>
                      <td className="py-1.5 tabular-nums">{(tr.target_weight * 100).toFixed(1)}%</td>
                      <td className="py-1.5 tabular-nums">${tr.dollar_trade.toLocaleString()}</td>
                      <td className="py-1.5 tabular-nums">{tr.share_trade}</td>
                      <td className="py-1.5 capitalize">
                        <span
                          className={
                            tr.action === "buy"
                              ? "text-[#7dff8e]"
                              : tr.action === "sell"
                                ? "text-red-400"
                                : "text-zinc-400"
                          }
                        >
                          {tr.action}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {rebalanceResult.constraint_violations.length > 0 && (
              <ul className="list-inside list-disc text-xs text-amber-300">
                {rebalanceResult.constraint_violations.map((v) => (
                  <li key={v}>{v}</li>
                ))}
              </ul>
            )}
          </div>
        )}
      </AsyncSection>
    </div>
  );
}
