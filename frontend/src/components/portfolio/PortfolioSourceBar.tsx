"use client";

import Link from "next/link";
import type { PortfolioSourceType, PortfolioSummaryResponse } from "@/lib/types";
import { formatFreshnessDate, parseSymbols, sourceLabel } from "@/lib/portfolioUtils";
import { useTranslation } from "@/lib/i18n";

interface PortfolioSourceBarProps {
  source: PortfolioSourceType;
  onSourceChange: (source: PortfolioSourceType) => void;
  symbolInput: string;
  onSymbolInputChange: (value: string) => void;
  onLoadWatchlist: () => void;
  watchlistSyms: string[];
  summary: PortfolioSummaryResponse | null;
  summaryLoading: boolean;
  summaryError: string | null;
  onRetrySummary: () => void;
  isHypothetical: boolean;
}

export function PortfolioSourceBar({
  source,
  onSourceChange,
  symbolInput,
  onSymbolInputChange,
  onLoadWatchlist,
  watchlistSyms,
  summary,
  summaryLoading,
  summaryError,
  onRetrySummary,
  isHypothetical,
}: PortfolioSourceBarProps) {
  const { t } = useTranslation();
  const symbols = parseSymbols(symbolInput);

  return (
    <div className="surface-card sticky top-0 z-10 space-y-3 border border-zinc-800/80 p-3 backdrop-blur-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t.portfolio.sourceLabel}
          </p>
          <p className="text-sm text-zinc-200">
            {sourceLabel(source)}
            {isHypothetical && (
              <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-200">
                {t.portfolio.hypothetical}
              </span>
            )}
          </p>
        </div>
        <div className="text-right text-xs text-zinc-500">
          {summaryLoading ? (
            <span>{t.common.loading}</span>
          ) : summaryError ? (
            <button type="button" onClick={onRetrySummary} className="text-red-400 underline">
              {t.common.retry}
            </button>
          ) : summary ? (
            <>
              <p>
                {t.portfolio.holdingsUpdated}: {formatFreshnessDate(summary.holdings_updated_at)}
              </p>
              <p>
                {t.portfolio.pricesThrough}: {formatFreshnessDate(summary.price_as_of ?? summary.last_price_update_at)}
              </p>
            </>
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {(["current", "watchlist", "custom"] as PortfolioSourceType[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => onSourceChange(s)}
            className={`rounded-lg px-3 py-1.5 text-xs ${
              source === s
                ? "bg-[#7dff8e]/15 text-[#7dff8e] ring-1 ring-[#7dff8e]/40"
                : "border border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {sourceLabel(s)}
          </button>
        ))}
      </div>

      {source !== "current" && (
        <div className="space-y-2">
          <textarea
            value={symbolInput}
            onChange={(e) => onSymbolInputChange(e.target.value)}
            rows={2}
            placeholder={t.portfolio.symbolsPlaceholder}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950/80 p-2 text-sm text-zinc-100"
            aria-label={t.portfolio.symbolsLabel}
          />
          <div className="flex flex-wrap gap-2">
            {source === "watchlist" && (
              <button type="button" onClick={onLoadWatchlist} className="btn-ghost px-3 py-1.5 text-xs">
                {t.portfolio.useWatchlist}
              </button>
            )}
            {watchlistSyms.slice(0, 12).map((sym) => (
              <button
                key={sym}
                type="button"
                onClick={() =>
                  onSymbolInputChange(
                    [...new Set([...parseSymbols(symbolInput), sym])].join(", ")
                  )
                }
                className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400 hover:border-zinc-500"
              >
                +{sym}
              </button>
            ))}
          </div>
          <p className="text-xs text-zinc-600">
            {symbols.length} symbol(s)
            {symbols.length > 0 && symbols.length < 2 ? t.portfolio.needTwo : ""}
          </p>
        </div>
      )}

      {source === "current" && summaryError && (
        <p className="text-sm text-red-400">{summaryError}</p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-800 pt-2">
        <p className="text-xs text-zinc-500">{t.portfolio.dailyDecisionsHint}</p>
        <Link href="/#daily-decisions" className="btn-ghost px-3 py-1 text-xs">
          {t.portfolio.viewDailyDecisions}
        </Link>
      </div>
    </div>
  );
}
