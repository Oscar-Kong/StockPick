// Results table for scan outputs with selection and watchlist actions.
"use client";

import { useTranslation } from "@/lib/i18n";
import type { StockResult } from "@/lib/types";
import clsx from "clsx";
import { ScanPickSummaryCell } from "./ScanPickSummaryCell";

interface StockTableProps {
  results: StockResult[];
  onSelect: (stock: StockResult) => void;
  onAddWatchlist: (stock: StockResult) => void;
  watchlistAdded?: Set<string>;
  watchlistPending?: string | null;
}

function riskBadge(risk: string) {
  return clsx(
    "rounded-full px-2 py-0.5 text-xs font-medium",
    risk === "high" && "bg-red-950/60 text-red-300",
    risk === "medium" && "bg-amber-950/60 text-amber-300",
    risk === "low" && "bg-emerald-950/70 text-emerald-300"
  );
}

function changeCell(value: unknown): string {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}%`;
}

function changeClass(value: unknown): string {
  const n = Number(value);
  if (Number.isNaN(n)) return "text-zinc-500";
  if (n > 0) return "text-[#7dff8e] font-medium";
  if (n < 0) return "text-red-400 font-medium";
  return "text-zinc-400";
}

export function StockTable({
  results,
  onSelect,
  onAddWatchlist,
  watchlistAdded,
  watchlistPending,
}: StockTableProps) {
  const { t } = useTranslation();

  const riskLabel = (risk: string) => {
    if (risk === "high") return t.risk.high;
    if (risk === "low") return t.risk.low;
    return t.risk.medium;
  };

  if (results.length === 0) {
    return (
      <div className="surface-card border-dashed p-10 text-center text-sm text-zinc-500">
        {t.scan.noResults}
      </div>
    );
  }

  return (
    <div className="surface-card overflow-hidden">
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
        <span>
          {results.length} {t.scan.candidatesRanked}
        </span>
        <span>{t.scan.tableHint}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-zinc-200 text-sm dark:divide-zinc-800">
          <thead className="sticky top-0 z-10 bg-zinc-950/95 backdrop-blur">
            <tr>
              <th className="px-3 py-3 text-left font-medium">#</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.symbol}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.price}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.score}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.risk}</th>
              <th className="px-3 py-3 text-center font-medium" title={t.scan.dayPct}>
                {t.scan.dayPct}
              </th>
              <th className="px-3 py-3 text-center font-medium" title={t.scan.weekPct}>
                {t.scan.weekPct}
              </th>
              <th className="px-3 py-3 text-center font-medium" title={t.scan.monthPct}>
                {t.scan.monthPct}
              </th>
              <th className="px-3 py-3 text-left font-medium w-[140px]">{t.scan.summary}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.watchlist}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 bg-transparent">
            {results.map((stock, idx) => {
              const added = watchlistAdded?.has(stock.symbol);
              const pending = watchlistPending === stock.symbol;
              const m = stock.metrics ?? {};

              return (
                <tr
                  key={stock.symbol}
                  className="cursor-pointer transition-colors hover:bg-[#00c805]/10"
                  onClick={() => onSelect(stock)}
                >
                  <td className="px-3 py-3 text-zinc-500">{idx + 1}</td>
                  <td className="px-3 py-3 font-semibold tracking-wide text-zinc-100">
                    {stock.symbol}
                  </td>
                  <td className="px-3 py-3">${stock.price.toFixed(2)}</td>
                  <td className="px-3 py-3">
                    <span className="font-medium">{stock.score.toFixed(1)}</span>
                  </td>
                  <td className="px-3 py-3">
                    <span className={riskBadge(stock.risk_level)}>{riskLabel(stock.risk_level)}</span>
                  </td>
                  <td className={clsx("px-3 py-3 text-center tabular-nums", changeClass(m.change_pct_1d))}>
                    {changeCell(m.change_pct_1d)}
                  </td>
                  <td className={clsx("px-3 py-3 text-center tabular-nums", changeClass(m.change_pct_1w))}>
                    {changeCell(m.change_pct_1w)}
                  </td>
                  <td className={clsx("px-3 py-3 text-center tabular-nums", changeClass(m.change_pct_1m))}>
                    {changeCell(m.change_pct_1m)}
                  </td>
                  <td className="px-3 py-3 align-top">
                    <ScanPickSummaryCell stock={stock} />
                  </td>
                  <td className="px-3 py-3">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (!added && !pending) onAddWatchlist(stock);
                      }}
                      disabled={added || pending}
                      className={clsx(
                        "min-w-[88px] rounded-lg px-2 py-1.5 text-xs font-medium transition",
                        added
                          ? "border border-[#00c805]/50 bg-[#00c805]/20 text-[#7dff8e]"
                          : pending
                            ? "border border-zinc-700 bg-zinc-900 text-zinc-400"
                            : "btn-ghost border border-zinc-700 hover:border-[#00c805]/50 hover:bg-[#00c805]/10 hover:text-[#7dff8e]"
                      )}
                    >
                      {pending ? t.scan.adding : added ? t.scan.added : t.scan.addWatchlist}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
