// Results table for scan outputs with selection and watchlist actions.
"use client";

import { RecommendationBadge } from "@/components/badges/RecommendationBadge";
import { RiskBadge } from "@/components/badges/RiskBadge";
import { ScoreBadge } from "@/components/badges/ScoreBadge";
import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { DenseTable, DenseTableToolbar } from "@/components/ui/DenseTable";
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

function HeldBadge({ position }: { position: HeldPositionSummary }) {
  const { t } = useTranslation();
  const sharesLabel =
    position.shares % 1 === 0
      ? String(position.shares)
      : position.shares.toFixed(2).replace(/\.?0+$/, "");

  return (
    <span
      className="mt-1 inline-flex items-center rounded-md border border-sky-500/40 bg-sky-500/10 px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-sky-200"
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
      <div className="surface-card border-dashed p-8 text-center text-sm text-secondary">
        {t.scan.noResults}
      </div>
    );
  }

  return (
    <div className="surface-card overflow-hidden">
      <DenseTableToolbar>
        <span>
          {results.length} {t.scan.candidatesRanked}
          {heldCount > 0 ? (
            <span className="ml-2 text-sky-300/90">
              · {fmt(t.scan.heldInResults, { count: heldCount })}
            </span>
          ) : null}
        </span>
        <span>{t.scan.tableHint}</span>
      </DenseTableToolbar>
      <DenseTable caption={t.scan.candidatesRanked}>
        <thead>
          <tr>
            <th className="col-num">#</th>
            <th>{t.scan.symbol}</th>
            <th className="col-num">{t.scan.price}</th>
            <th className="col-num">{t.scan.score}</th>
            <th className="hidden lg:table-cell">{t.scanDrawer.source}</th>
            <th>{t.scan.risk}</th>
            <th className="hidden xl:table-cell">{t.scanDrawer.topFactors}</th>
            <th className="col-num" title={t.scan.dayPct}>
              {t.scan.dayPct}
            </th>
            <th className="w-[120px]">{t.scan.summary}</th>
            <th>{t.scan.watchlist}</th>
          </tr>
        </thead>
        <tbody>
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
                className={clsx("cursor-pointer", held && "is-selected")}
                onClick={() => onSelect(stock)}
              >
                <td className="col-num text-secondary">{idx + 1}</td>
                <td>
                  <span className="font-semibold tracking-wide text-zinc-100">{stock.symbol}</span>
                  {held && <HeldBadge position={held} />}
                  {rec && (
                    <div className="mt-1">
                      <RecommendationBadge recommendation={rec} />
                    </div>
                  )}
                </td>
                <td className="col-num finance-value">${stock.price.toFixed(2)}</td>
                <td className="col-num">
                  <ScoreBadge score={stock.score} />
                </td>
                <td className="hidden lg:table-cell">
                  {scoreSource && <ScoreSourceBadge source={scoreSource} />}
                </td>
                <td>
                  <RiskBadge level={stock.risk_level} />
                </td>
                <td className="hidden text-sm text-secondary xl:table-cell">
                  {factors.map((f) => (
                    <div key={f.name}>{f.name}</div>
                  ))}
                  {warnings.map((f) => (
                    <div key={f.name} className="text-amber-300/90">
                      ⚠ {f.name}
                    </div>
                  ))}
                </td>
                <td className={clsx("col-num finance-value", changeClass(m.change_pct_1d))}>
                  {changeCell(m.change_pct_1d)}
                </td>
                <td className="align-top">
                  <ScanPickSummaryCell stock={stock} />
                </td>
                <td>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!added && !pending) onAddWatchlist(stock);
                    }}
                    disabled={added || pending}
                    aria-label={`${t.scan.addWatchlist} ${stock.symbol}`}
                    className={clsx(
                      "min-h-[2.5rem] min-w-[5.5rem] rounded-lg px-2.5 py-1.5 text-sm font-medium transition",
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
      </DenseTable>
    </div>
  );
}
