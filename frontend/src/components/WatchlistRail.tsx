// Compact sticky watchlist sidebar for Workspace research view.
"use client";

import { WatchlistImport } from "@/components/WatchlistImport";
import type { AnalyzeWatchlistRow, WatchlistItem } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import clsx from "clsx";
import Link from "next/link";

interface WatchlistRailProps {
  items: WatchlistItem[];
  matrixBySymbol: Map<string, AnalyzeWatchlistRow>;
  selected: string | null;
  filter: string;
  onFilterChange: (value: string) => void;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
  onRefresh: () => void;
  onToggleImport: () => void;
  showImport: boolean;
  refreshing: boolean;
  loading: boolean;
  msg: string | null;
  onImported?: () => void;
}

export function WatchlistRail({
  items,
  matrixBySymbol,
  selected,
  filter,
  onFilterChange,
  onSelect,
  onRemove,
  onRefresh,
  onToggleImport,
  showImport,
  refreshing,
  loading,
  msg,
  onImported,
}: WatchlistRailProps) {
  const { t } = useTranslation();
  const filtered = items.filter(
    (i) =>
      !filter ||
      i.symbol.includes(filter.toUpperCase()) ||
      (i.notes || "").toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div className="flex h-full min-h-0 w-full flex-col overflow-hidden">
      <div className="shrink-0 space-y-1.5 border-b border-zinc-800 p-2.5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-zinc-200">{t.watchlist.title}</h2>
          <span className="text-xs text-zinc-500">{filtered.length}</span>
        </div>
        <div className="flex gap-1.5">
          <button type="button" onClick={onToggleImport} className="btn-primary flex-1 px-2 py-1.5 text-xs">
            {showImport ? t.common.close : t.watchlist.add}
          </button>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing || items.length === 0}
            className="btn-ghost px-2 py-1.5 text-xs disabled:opacity-50"
            title={t.watchlist.refreshTitle}
          >
            {refreshing ? "…" : "↻"}
          </button>
        </div>
        <input
          type="search"
          placeholder={t.watchlist.filterPlaceholder}
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          className="input-field py-1.5 text-xs"
        />
        {msg && <p className="text-xs text-zinc-500">{msg}</p>}
      </div>

      {showImport && onImported && (
        <div className="max-h-48 shrink-0 overflow-y-auto border-b border-zinc-800 p-3">
          <WatchlistImport onImported={onImported} />
        </div>
      )}

      <div className="watchlist-rail-scroll min-h-0 flex-1 overflow-y-auto overscroll-contain">
        {loading ? (
          <p className="p-4 text-xs text-zinc-500">{t.common.loading}</p>
        ) : filtered.length === 0 ? (
          <p className="p-4 text-center text-xs text-zinc-500">{t.watchlist.empty}</p>
        ) : (
          <ul>
            {filtered.map((item) => {
              const row = matrixBySymbol.get(item.symbol);
              const active = selected === item.symbol;
              const tech = row?.technicals;
              const alertCount = row?.alert_count ?? 0;

              return (
                <li key={item.symbol} className="border-b border-zinc-900/80">
                  <button
                    type="button"
                    onClick={() => onSelect(item.symbol)}
                    className={clsx(
                      "w-full px-3 py-2.5 text-left transition",
                      active ? "watchlist-item--active" : "hover:bg-zinc-900/50"
                    )}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold tracking-wide text-zinc-100">
                            {item.symbol}
                          </span>
                          {alertCount > 0 && (
                            <span className="rounded-full bg-amber-500/20 px-1.5 text-xs text-amber-300">
                              {alertCount}
                            </span>
                          )}
                          {row?.stale && (
                            <span className="text-xs text-zinc-600" title={t.common.staleData}>
                              ○
                            </span>
                          )}
                        </div>
                        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-zinc-500">
                          <span className="capitalize text-[#7dff8e]/90">{item.bucket}</span>
                          {item.price != null && (
                            <span className="tabular-nums">${item.price.toFixed(2)}</span>
                          )}
                          {tech?.rs_vs_spy != null && (
                            <span>RS {tech.rs_vs_spy.toFixed(0)}</span>
                          )}
                        </div>
                      </div>
                      <div className="shrink-0 text-right">
                        <p
                          className={clsx(
                            "text-sm font-semibold tabular-nums",
                            (item.score ?? 0) >= 60
                              ? "text-[#7dff8e]"
                              : (item.score ?? 0) >= 40
                                ? "text-zinc-200"
                                : "text-zinc-500"
                          )}
                        >
                          {item.score != null ? item.score.toFixed(0) : "—"}
                        </p>
                        <p className="text-xs text-zinc-600">{t.watchlist.scoreLabel}</p>
                      </div>
                    </div>
                    {(row?.summary || item.notes) && (
                      <p className="mt-1 line-clamp-1 text-xs text-zinc-600">
                        {row?.summary || item.notes}
                      </p>
                    )}
                  </button>
                  <div className="flex items-center gap-3 px-3 pb-2 text-xs">
                    <Link
                      href={`/scan?bucket=${item.bucket}`}
                      className="text-zinc-500 underline hover:text-zinc-300"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t.watchlist.scanLink}
                    </Link>
                    <button
                      type="button"
                      onClick={() => onRemove(item.symbol)}
                      className="text-zinc-600 underline hover:text-red-400"
                    >
                      {t.common.remove}
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
