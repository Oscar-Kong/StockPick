// Results table for scan outputs with selection and watchlist actions.
"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { ScanScoreBreakdown } from "@/components/scan/ScanScoreBreakdown";
import { ScanTradeHintCell } from "@/components/scan/ScanTradeHintCell";
import { DenseTable, DenseTableToolbar } from "@/components/ui/DenseTable";
import { fmt, useTranslation } from "@/lib/i18n";
import type { HeldPositionSummary, StockResult } from "@/lib/types";
import clsx from "clsx";
import { useRouter } from "next/navigation";
import { useMemo, useState, type ReactNode } from "react";

interface StockTableProps {
  results: StockResult[];
  onAddWatchlist: (stock: StockResult) => void;
  watchlistAdded?: Set<string>;
  watchlistPending?: string | null;
  heldPositions?: ReadonlyMap<string, HeldPositionSummary>;
  scoringEngineUsed?: boolean | null;
}

type ColumnId =
  | "rank"
  | "symbol"
  | "recommendation"
  | "score"
  | "price"
  | "change"
  | "factor"
  | "warning"
  | "thesis"
  | "watchlist"
  | "source";

const DEFAULT_COLUMNS: ColumnId[] = [
  "rank",
  "symbol",
  "recommendation",
  "score",
  "price",
  "change",
  "factor",
  "warning",
  "thesis",
  "watchlist",
];

const OPTIONAL_COLUMNS: ColumnId[] = ["source"];

/** Shared width hints — thead/tbody/colgroup must stay in lockstep. */
const COLUMN_WIDTH: Record<ColumnId, string> = {
  rank: "2.75rem",
  symbol: "6.5rem",
  recommendation: "5.75rem",
  score: "5.5rem",
  price: "4.75rem",
  change: "4.25rem",
  factor: "7rem",
  warning: "7rem",
  thesis: "auto",
  watchlist: "3.25rem",
  source: "5.5rem",
};

/** Compact columns — centered header + cell (often "—"). */
const CENTER_COLUMNS = new Set<ColumnId>(["recommendation", "factor", "warning", "source"]);

const ALL_COLUMNS: ColumnId[] = [...DEFAULT_COLUMNS, ...OPTIONAL_COLUMNS];

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

function topFactor(stock: StockResult) {
  return [...stock.signals]
    .filter((s) => s.contribution > 0)
    .sort((a, b) => b.contribution - a.contribution)[0];
}

function topWarning(stock: StockResult) {
  return [...stock.signals]
    .filter((s) => s.contribution < 0)
    .sort((a, b) => a.contribution - b.contribution)[0];
}

function thesisText(stock: StockResult): string {
  const s = stock.summary?.trim();
  if (s) return s.length > 120 ? `${s.slice(0, 117)}…` : s;
  return "—";
}

function HeldBadge({ position }: { position: HeldPositionSummary }) {
  const { t } = useTranslation();
  const sharesLabel =
    position.shares % 1 === 0
      ? String(position.shares)
      : position.shares.toFixed(2).replace(/\.?0+$/, "");

  return (
    <span
      className="ml-1.5 inline-flex items-center rounded border border-sky-500/40 bg-sky-500/10 px-1 py-0.5 text-xs font-semibold uppercase text-sky-200"
      title={fmt(t.scan.heldTooltip, { shares: sharesLabel })}
    >
      {fmt(t.scan.heldBadge, { shares: sharesLabel })}
    </span>
  );
}

export function StockTable({
  results,
  onAddWatchlist,
  watchlistAdded,
  watchlistPending,
  heldPositions,
  scoringEngineUsed,
}: StockTableProps) {
  const { t } = useTranslation();
  const router = useRouter();
  const [columnsOpen, setColumnsOpen] = useState(false);
  const [visible, setVisible] = useState<Set<ColumnId>>(() => new Set(DEFAULT_COLUMNS));

  const scoreSource =
    scoringEngineUsed === true
      ? "scoring_engine_v2"
      : scoringEngineUsed === false
        ? "legacy_screener"
        : null;

  const heldCount = heldPositions
    ? results.filter((r) => heldPositions.has(r.symbol.toUpperCase())).length
    : 0;

  const columnLabels: Record<ColumnId, string> = useMemo(
    () => ({
      rank: "#",
      symbol: t.scan.symbol,
      recommendation: t.scan.recommendationCol,
      score: t.scan.score,
      price: t.scan.price,
      change: t.scan.dayPct,
      factor: t.scan.mainFactorCol,
      warning: t.scan.mainWarningCol,
      thesis: t.scan.summary,
      watchlist: t.scan.watchlist,
      source: t.scanDrawer.source,
    }),
    [t]
  );

  const show = (id: ColumnId) => visible.has(id);

  const visibleColumns = ALL_COLUMNS.filter((id) => show(id));

  const thClass = (id: ColumnId) =>
    clsx(
      id === "rank" || id === "score" || id === "price" || id === "change" ? "col-num" : "",
      CENTER_COLUMNS.has(id) && "scan-col-center",
      id === "thesis" && "scan-col-thesis",
      id === "watchlist" && "scan-col-watchlist"
    );

  const tdClass = (id: ColumnId) => thClass(id);

  const emptyCell = <span className="scan-empty-cell">—</span>;

  const toggleColumn = (id: ColumnId) => {
    setVisible((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  if (results.length === 0) {
    return (
      <div className="scan-results-empty surface-card border-dashed p-6 text-center text-sm text-secondary">
        {t.scan.noResults}
      </div>
    );
  }

  return (
    <div className="scan-results-table surface-card flex min-h-0 flex-1 flex-col overflow-hidden">
      <DenseTableToolbar>
        <span>
          {results.length} {t.scan.candidatesRanked}
          {heldCount > 0 ? (
            <span className="ml-2 text-sky-300/90">
              · {fmt(t.scan.heldInResults, { count: heldCount })}
            </span>
          ) : null}
        </span>
        <div className="relative">
          <button
            type="button"
            className="scan-command-bar__btn"
            onClick={() => setColumnsOpen((o) => !o)}
            aria-expanded={columnsOpen}
          >
            {t.scan.columnsMenu}
          </button>
          {columnsOpen && (
            <div className="scan-columns-menu">
              {[...DEFAULT_COLUMNS, ...OPTIONAL_COLUMNS].map((id) => (
                <label key={id} className="scan-columns-menu__item">
                  <input
                    type="checkbox"
                    checked={visible.has(id)}
                    onChange={() => toggleColumn(id)}
                    disabled={id === "rank" || id === "symbol"}
                  />
                  {columnLabels[id]}
                </label>
              ))}
            </div>
          )}
        </div>
      </DenseTableToolbar>
      <div className="scan-results-table__scroll min-h-0 flex-1 overflow-auto">
        <DenseTable caption={t.scan.candidatesRanked} className="scan-results-table__grid">
          <colgroup>
            {visibleColumns.map((id) => (
              <col
                key={id}
                className={CENTER_COLUMNS.has(id) ? "scan-col-center" : undefined}
                style={id === "thesis" ? undefined : { width: COLUMN_WIDTH[id] }}
              />
            ))}
          </colgroup>
          <thead>
            <tr>
              {visibleColumns.map((id) => (
                <th key={id} className={thClass(id)}>
                  {columnLabels[id]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((stock, idx) => {
              const added = watchlistAdded?.has(stock.symbol);
              const pending = watchlistPending === stock.symbol;
              const held = heldPositions?.get(stock.symbol.toUpperCase());
              const m = stock.metrics ?? {};
              const factor = topFactor(stock);
              const warning = topWarning(stock);
              const thesis = thesisText(stock);

              const cells: Record<ColumnId, ReactNode> = {
                rank: <span className="text-secondary">{idx + 1}</span>,
                symbol: (
                  <>
                    <span className="font-semibold tracking-wide text-zinc-100">{stock.symbol}</span>
                    {held && <HeldBadge position={held} />}
                  </>
                ),
                recommendation: <ScanTradeHintCell stock={stock} compact />,
                score: (
                  <ScanScoreBreakdown stock={stock} compact />
                ),
                price: <span className="finance-value">${stock.price.toFixed(2)}</span>,
                change: (
                  <span className={clsx("finance-value", changeClass(m.change_pct_1d))}>
                    {changeCell(m.change_pct_1d)}
                  </span>
                ),
                factor: factor?.name ? (
                  <span className="block truncate text-sm text-secondary" title={factor.name}>
                    {factor.name}
                  </span>
                ) : (
                  emptyCell
                ),
                warning: warning?.name ? (
                  <span className="block truncate text-sm text-amber-300/90" title={warning.name}>
                    ⚠ {warning.name}
                  </span>
                ) : (
                  emptyCell
                ),
                thesis: (
                  <span className="block text-sm leading-snug text-secondary line-clamp-2" title={stock.summary}>
                    {thesis === "—" ? emptyCell : thesis}
                  </span>
                ),
                source: scoreSource ? <ScoreSourceBadge source={scoreSource} /> : emptyCell,
                watchlist: (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (!added && !pending) onAddWatchlist(stock);
                    }}
                    disabled={added || pending}
                    aria-label={`${t.scan.addWatchlist} ${stock.symbol}`}
                    title={added ? t.scan.added : t.scan.addWatchlist}
                    className={clsx(
                      "scan-watchlist-btn",
                      added && "scan-watchlist-btn--added",
                      pending && "scan-watchlist-btn--pending"
                    )}
                  >
                    {pending ? "…" : added ? "✓" : "+"}
                  </button>
                ),
              };

              return (
                <tr
                  key={stock.symbol}
                  className={clsx("scan-results-row scan-results-row--link", held && "is-held")}
                  onClick={() => router.push(`/workspace?symbol=${encodeURIComponent(stock.symbol)}`)}
                >
                  {visibleColumns.map((id) => (
                    <td key={id} className={tdClass(id)}>
                      {cells[id]}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </DenseTable>
      </div>
    </div>
  );
}
