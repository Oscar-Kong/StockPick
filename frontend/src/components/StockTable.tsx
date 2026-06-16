// Results table for scan outputs with selection and watchlist actions.
"use client";

import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { RiskBadge } from "@/components/badges/RiskBadge";
import { ScoreBadge } from "@/components/badges/ScoreBadge";
import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { fmt, useTranslation } from "@/lib/i18n";
import type { HeldPositionSummary, StockResult } from "@/lib/types";
import clsx from "clsx";
import { ScanPickSummaryCell } from "./ScanPickSummaryCell";

interface StockTableProps {
  results: StockResult[];
  onSelect: (stock: StockResult) => void;
  onAddWatchlist: (stock: StockResult) => void;
  watchlistAdded?: Set<string>;
  watchlistPending?: string | null;
  heldPositions?: ReadonlyMap<string, HeldPositionSummary>;
  scoringEngineUsed?: boolean | null;
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

function topFactors(stock: StockResult, n: number) {
  return [...stock.signals]
    .filter((s) => s.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)
    .slice(0, n);
}

function topWarnings(stock: StockResult, n: number) {
  return [...stock.signals]
    .filter((s) => s.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution)
    .slice(0, n);
}

function HeldBadge({
  position,
}: {
  position: HeldPositionSummary;
}) {
  const { t } = useTranslation();
  const sharesLabel =
    position.shares % 1 === 0
      ? String(position.shares)
      : position.shares.toFixed(2).replace(/\.?0+$/, "");

  return (
    <span
      className="mt-1 inline-flex items-center rounded-md border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-200"
      title={fmt(t.scan.heldTooltip, { shares: sharesLabel })}
    >
      {fmt(t.scan.heldBadge, { shares: sharesLabel })}
    </span>
  );
}

export function StockTable({
  results,
  onSelect,
  onAddWatchlist,
  watchlistAdded,
  watchlistPending,
  heldPositions,
  scoringEngineUsed,
}: StockTableProps) {
  const { t } = useTranslation();
  const scoreSource =
    scoringEngineUsed === true
      ? "scoring_engine_v2"
      : scoringEngineUsed === false
        ? "legacy_screener"
        : null;

  const heldCount = heldPositions
    ? results.filter((r) => heldPositions.has(r.symbol.toUpperCase())).length
    : 0;

  if (results.length === 0) {
    return (
      <div className="surface-card border-dashed p-10 text-center text-sm text-zinc-500">
        {t.scan.noResults}
      </div>
    );
  }

  return (
    <div className="surface-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800 px-4 py-2 text-xs text-zinc-500">
        <span>
          {results.length} {t.scan.candidatesRanked}
          {heldCount > 0 ? (
            <span className="ml-2 text-sky-300/90">
              · {fmt(t.scan.heldInResults, { count: heldCount })}
            </span>
          ) : null}
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
              <th className="hidden px-3 py-3 text-left font-medium lg:table-cell">{t.scanDrawer.source}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.risk}</th>
              <th className="hidden px-3 py-3 text-left font-medium xl:table-cell">{t.scanDrawer.topFactors}</th>
              <th className="px-3 py-3 text-center font-medium" title={t.scan.dayPct}>
                {t.scan.dayPct}
              </th>
              <th className="px-3 py-3 text-left font-medium w-[120px]">{t.scan.summary}</th>
              <th className="px-3 py-3 text-left font-medium">{t.scan.watchlist}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-900 bg-transparent">
            {results.map((stock, idx) => {
              const added = watchlistAdded?.has(stock.symbol);
              const pending = watchlistPending === stock.symbol;
              const held = heldPositions?.get(stock.symbol.toUpperCase());
              const m = stock.metrics ?? {};
              const rec = m.recommendation as string | undefined;
              const factors = topFactors(stock, 2);
              const warnings = topWarnings(stock, 1);

              return (
                <tr
                  key={stock.symbol}
                  className={clsx(
                    "cursor-pointer transition-colors hover:bg-[#00c805]/10",
                    held && "bg-sky-500/[0.04]"
                  )}
                  onClick={() => onSelect(stock)}
                >
                  <td className="px-3 py-3 text-zinc-500">{idx + 1}</td>
                  <td className="px-3 py-3">
                    <span className="font-semibold tracking-wide text-zinc-100">{stock.symbol}</span>
                    {held && <HeldBadge position={held} />}
                    {rec && (
                      <div className="mt-1">
                        <RecommendationBadge recommendation={rec} />
                      </div>
                    )}
                  </td>
                  <td className="px-3 py-3 tabular-nums">${stock.price.toFixed(2)}</td>
                  <td className="px-3 py-3">
                    <ScoreBadge score={stock.score} />
                  </td>
                  <td className="hidden px-3 py-3 lg:table-cell">
                    {scoreSource && <ScoreSourceBadge source={scoreSource} />}
                  </td>
                  <td className="px-3 py-3">
                    <RiskBadge level={stock.risk_level} />
                  </td>
                  <td className="hidden px-3 py-3 text-xs text-zinc-500 xl:table-cell">
                    {factors.map((f) => (
                      <div key={f.name}>{f.name}</div>
                    ))}
                    {warnings.map((f) => (
                      <div key={f.name} className="text-amber-300/80">
                        ⚠ {f.name}
                      </div>
                    ))}
                  </td>
                  <td className={clsx("px-3 py-3 text-center tabular-nums", changeClass(m.change_pct_1d))}>
                    {changeCell(m.change_pct_1d)}
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
