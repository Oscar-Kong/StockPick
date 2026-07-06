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

function RefreshIcon() {
  return (
    <svg aria-hidden viewBox="0 0 16 16" className="watchlist-rail__icon" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M2.5 8a5.5 5.5 0 0 1 9.3-3.9L13 5" strokeLinecap="round" />
      <path d="M13.5 8a5.5 5.5 0 0 1-9.3 3.9L3 11" strokeLinecap="round" />
      <path d="M11.5 2v3h-3M4.5 14v-3h3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function scoreTone(score: number | null | undefined): string {
  if (score == null) return "text-zinc-500";
  if (score >= 60) return "text-buy";
  if (score >= 40) return "text-zinc-200";
  return "text-zinc-500";
}

function WatchlistSkeleton() {
  return (
    <ul className="watchlist-rail__list" aria-hidden>
      {[0, 1, 2, 3, 4].map((i) => (
        <li key={i} className="watchlist-rail__skeleton-row">
          <div className="watchlist-rail__skeleton-line watchlist-rail__skeleton-line--symbol" />
          <div className="watchlist-rail__skeleton-line watchlist-rail__skeleton-line--meta" />
        </li>
      ))}
    </ul>
  );
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
      (i.notes || "").toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="watchlist-rail">
      <div className="watchlist-rail__header">
        <div className="watchlist-rail__title-row">
          <h2 className="watchlist-rail__title">{t.watchlist.title}</h2>
          <span className="watchlist-rail__count">{filtered.length}</span>
        </div>
        <div className="watchlist-rail__actions">
          <button type="button" onClick={onToggleImport} className="btn-primary watchlist-rail__add-btn">
            {showImport ? t.common.close : t.watchlist.add}
          </button>
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing || items.length === 0}
            className="watchlist-rail__refresh-btn"
            title={t.watchlist.refreshTitle}
            aria-label={t.watchlist.refreshTitle}
          >
            {refreshing ? <span className="watchlist-rail__spin">…</span> : <RefreshIcon />}
          </button>
        </div>
        <input
          type="search"
          placeholder={t.watchlist.filterPlaceholder}
          value={filter}
          onChange={(e) => onFilterChange(e.target.value)}
          className="watchlist-rail__search input-field"
        />
        {msg && <p className="watchlist-rail__msg">{msg}</p>}
      </div>

      {showImport && onImported && (
        <div className="watchlist-rail__import">
          <WatchlistImport onImported={onImported} />
        </div>
      )}

      <div className="watchlist-rail-scroll watchlist-rail__scroll">
        {loading ? (
          <WatchlistSkeleton />
        ) : filtered.length === 0 ? (
          <p className="watchlist-rail__empty">{t.watchlist.empty}</p>
        ) : (
          <ul className="watchlist-rail__list">
            {filtered.map((item) => {
              const row = matrixBySymbol.get(item.symbol);
              const active = selected === item.symbol;
              const tech = row?.technicals;
              const alertCount = row?.alert_count ?? 0;
              const score = item.score;
              const scorePct = score != null ? Math.min(100, Math.max(0, score)) : 0;

              return (
                <li key={item.symbol} className="watchlist-rail__item">
                  <button
                    type="button"
                    onClick={() => onSelect(item.symbol)}
                    className={clsx("watchlist-rail__row", active && "watchlist-rail__row--active")}
                    aria-current={active ? "true" : undefined}
                  >
                    <div className="watchlist-rail__row-main">
                      <div className="watchlist-rail__symbol-block">
                        <div className="watchlist-rail__symbol-line">
                          <span className="watchlist-rail__symbol">{item.symbol}</span>
                          {alertCount > 0 && (
                            <span className="watchlist-rail__alert-badge">{alertCount}</span>
                          )}
                          {row?.stale && (
                            <span className="watchlist-rail__stale-dot" title={t.common.staleData} aria-label={t.common.staleData} />
                          )}
                        </div>
                        <div className="watchlist-rail__meta">
                          <span className="watchlist-rail__bucket">{item.bucket}</span>
                          {item.price != null && (
                            <span className="watchlist-rail__price">${item.price.toFixed(2)}</span>
                          )}
                          {tech?.rs_vs_spy != null && (
                            <span className="watchlist-rail__rs">RS {tech.rs_vs_spy.toFixed(0)}</span>
                          )}
                        </div>
                      </div>
                      <div className="watchlist-rail__score-block">
                        <span className={clsx("watchlist-rail__score finance-value", scoreTone(score))}>
                          {score != null ? score.toFixed(0) : "—"}
                        </span>
                        <div className="watchlist-rail__score-bar" aria-hidden>
                          <span
                            className="watchlist-rail__score-fill"
                            style={{ width: `${scorePct}%` }}
                          />
                        </div>
                      </div>
                    </div>
                    {(row?.summary || item.notes) && (
                      <p className="watchlist-rail__summary">{row?.summary || item.notes}</p>
                    )}
                  </button>
                  <div className="watchlist-rail__row-actions">
                    <Link
                      href={`/scan?bucket=${item.bucket}`}
                      className="watchlist-rail__link"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {t.watchlist.scanLink}
                    </Link>
                    <button
                      type="button"
                      onClick={() => onRemove(item.symbol)}
                      className="watchlist-rail__remove"
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
