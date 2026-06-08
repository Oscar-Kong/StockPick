// Side-by-side peer comparison (2–4 symbols) with a clear metrics table.
"use client";

import { getAnalyzeCompare } from "@/lib/api";
import { fmt, useTranslation } from "@/lib/i18n";
import type { Messages } from "@/lib/i18n/messages/en";
import type { AnalyzeCompareEntry, AnalyzeCompareResponse, AnalyzeWatchlistRow } from "@/lib/types";
import clsx from "clsx";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

const MAX_SYMBOLS = 4;

interface ComparePanelProps {
  watchlistRows?: AnalyzeWatchlistRow[];
  initialSymbols?: string[];
}

type MetricId = keyof Messages["compare"]["metrics"];

type MetricRow = {
  id: MetricId;
  label: string;
  format: (e: AnalyzeCompareEntry) => string;
  /** Higher is better for highlighting the winner. */
  higherIsBetter?: boolean;
  /** Lower is better (e.g. distance from 52w high). */
  lowerIsBetter?: boolean;
};

function fmtNum(v: number | null | undefined, digits = 1): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function bestSymbol(
  entries: AnalyzeCompareEntry[],
  pick: (e: AnalyzeCompareEntry) => number | null | undefined,
  mode: "max" | "min"
): string | null {
  let best: { sym: string; val: number } | null = null;
  for (const e of entries) {
    if (e.error) continue;
    const v = pick(e);
    if (v == null || Number.isNaN(v)) continue;
    if (!best || (mode === "max" ? v > best.val : v < best.val)) {
      best = { sym: e.symbol, val: v };
    }
  }
  return best?.sym ?? null;
}

export function ComparePanel({ watchlistRows = [], initialSymbols = [] }: ComparePanelProps) {
  const { t } = useTranslation();

  const riskLabel = useCallback(
    (level: string | null | undefined) => {
      if (!level) return "—";
      if (level === "high") return t.risk.high;
      if (level === "low") return t.risk.low;
      return t.risk.medium;
    },
    [t]
  );

  const METRIC_ROWS = useMemo((): MetricRow[] => {
    const m = t.compare.metrics;
    return [
      {
        id: "watchlistScore",
        label: m.watchlistScore,
        format: (e) => fmtNum(e.score, 1),
        higherIsBetter: true,
      },
      {
        id: "bucket",
        label: m.bucket,
        format: (e) => (e.assigned_bucket ? e.assigned_bucket : "—"),
      },
      {
        id: "price",
        label: m.price,
        format: (e) => (e.price != null ? `$${e.price.toFixed(2)}` : "—"),
      },
      {
        id: "dataQuality",
        label: m.dataQuality,
        format: (e) => (e.reconcile_quality != null ? `${e.reconcile_quality.toFixed(0)}%` : "—"),
        higherIsBetter: true,
      },
      {
        id: "rsVsSpy",
        label: m.rsVsSpy,
        format: (e) => fmtNum(e.technicals?.rs_vs_spy, 0),
        higherIsBetter: true,
      },
      {
        id: "trendScore",
        label: m.trendScore,
        format: (e) => fmtNum(e.technicals?.trend_score, 0),
        higherIsBetter: true,
      },
      {
        id: "breakoutScore",
        label: m.breakoutScore,
        format: (e) => fmtNum(e.technicals?.breakout_score, 0),
        higherIsBetter: true,
      },
      {
        id: "pctFromHigh",
        label: m.pctFromHigh,
        format: (e) =>
          e.technicals?.pct_from_52w_high != null
            ? `${e.technicals.pct_from_52w_high.toFixed(1)}%`
            : "—",
        higherIsBetter: true,
      },
      {
        id: "peReconciled",
        label: m.peReconciled,
        format: (e) => fmtNum(e.canonical?.pe_ratio as number | undefined, 1),
      },
      {
        id: "marketCap",
        label: m.marketCap,
        format: (e) => {
          const cap = e.canonical?.market_cap as number | undefined;
          if (cap == null) return "—";
          if (cap >= 1e12) return `$${(cap / 1e12).toFixed(2)}T`;
          if (cap >= 1e9) return `$${(cap / 1e9).toFixed(2)}B`;
          if (cap >= 1e6) return `$${(cap / 1e6).toFixed(0)}M`;
          return `$${cap.toFixed(0)}`;
        },
      },
      {
        id: "alerts",
        label: m.alerts,
        format: (e) => String(e.alert_count ?? 0),
        lowerIsBetter: true,
      },
      {
        id: "risk",
        label: m.risk,
        format: (e) => riskLabel(e.risk_level),
      },
    ];
  }, [t, riskLabel]);

  const [picked, setPicked] = useState<string[]>(() =>
    initialSymbols.map((s) => s.toUpperCase()).slice(0, MAX_SYMBOLS)
  );
  const [customInput, setCustomInput] = useState("");
  const [data, setData] = useState<AnalyzeCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialSymbols.length) {
      setPicked(initialSymbols.map((s) => s.toUpperCase()).slice(0, MAX_SYMBOLS));
    }
  }, [initialSymbols.join(",")]);

  const toggleSymbol = (sym: string) => {
    const upper = sym.toUpperCase();
    setPicked((prev) => {
      if (prev.includes(upper)) return prev.filter((s) => s !== upper);
      if (prev.length >= MAX_SYMBOLS) return [...prev.slice(1), upper];
      return [...prev, upper];
    });
  };

  const addCustom = () => {
    const parts = customInput
      .split(/[,\s]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);
    if (!parts.length) return;
    setPicked((prev) => {
      const merged = [...prev];
      for (const s of parts) {
        if (merged.includes(s)) continue;
        if (merged.length >= MAX_SYMBOLS) merged.shift();
        merged.push(s);
      }
      return merged;
    });
    setCustomInput("");
  };

  const run = useCallback(async () => {
    if (picked.length < 2) {
      setError(t.compare.pickTwo);
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getAnalyzeCompare(picked));
    } catch (err) {
      setError(err instanceof Error ? err.message : t.compare.failed);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [picked, t]);

  const winnersByRow = useMemo(() => {
    if (!data?.entries.length) return {} as Record<MetricId, string | null>;
    const map: Record<MetricId, string | null> = {} as Record<MetricId, string | null>;
    for (const row of METRIC_ROWS) {
      if (row.higherIsBetter) {
        map[row.id] = bestSymbol(data.entries, (e) => {
          if (row.id === "watchlistScore") return e.score ?? null;
          if (row.id === "dataQuality") return e.reconcile_quality ?? null;
          if (row.id === "rsVsSpy") return e.technicals?.rs_vs_spy ?? null;
          if (row.id === "trendScore") return e.technicals?.trend_score ?? null;
          if (row.id === "breakoutScore") return e.technicals?.breakout_score ?? null;
          if (row.id === "pctFromHigh") return e.technicals?.pct_from_52w_high ?? null;
          return null;
        }, "max");
      } else if (row.lowerIsBetter) {
        map[row.id] = bestSymbol(data.entries, (e) => {
          if (row.id === "peReconciled") return (e.canonical?.pe_ratio as number) ?? null;
          if (row.id === "alerts") return e.alert_count ?? null;
          return null;
        }, "min");
      }
    }
    return map;
  }, [data, METRIC_ROWS]);

  const highlights = data?.highlights ?? {};

  return (
    <div className="space-y-4">
      <div className="surface-card space-y-3 p-4">
        <h2 className="text-sm font-semibold text-zinc-100">{t.compare.title}</h2>
        <p className="text-xs text-zinc-500">{t.compare.description}</p>

        {watchlistRows.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {watchlistRows.map((row) => {
              const on = picked.includes(row.symbol);
              return (
                <button
                  key={row.symbol}
                  type="button"
                  onClick={() => toggleSymbol(row.symbol)}
                  className={clsx(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition",
                    on
                      ? "border-[#00c805] bg-[#00c805]/20 text-[#7dff8e]"
                      : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                  )}
                >
                  {row.symbol}
                  {row.score != null ? ` · ${row.score.toFixed(0)}` : ""}
                </button>
              );
            })}
          </div>
        )}

        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={customInput}
            onChange={(e) => setCustomInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCustom()}
            placeholder={t.compare.inputPlaceholder}
            className="min-w-[160px] flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
          />
          <button type="button" onClick={addCustom} className="btn-ghost px-3 py-2 text-sm">
            {t.common.add}
          </button>
          <button
            type="button"
            onClick={run}
            disabled={loading || picked.length < 2}
            className="btn-primary px-4 py-2 text-sm disabled:opacity-50"
          >
            {loading
              ? t.compare.comparing
              : fmt(t.compare.compareBtn, { count: picked.length })}
          </button>
        </div>

        {picked.length > 0 && (
          <p className="text-xs text-zinc-500">
            {picked.length < 2
              ? fmt(t.compare.selectedNeedTwo, { list: picked.join(", ") })
              : `${picked.join(", ")}`}
          </p>
        )}
      </div>

      {error && <p className="text-sm text-red-400">{error}</p>}

      {data && data.entries.length > 0 && (
        <>
          {(highlights.highest_score || highlights.best_rs_vs_spy) && (
            <div className="flex flex-wrap gap-2 text-xs">
              {highlights.highest_score && (
                <span className="rounded-full border border-[#00c805]/50 bg-zinc-900 px-2 py-1 text-zinc-100">
                  <span className="text-[#7dff8e]">{t.compare.topScore}</span> {highlights.highest_score}
                </span>
              )}
              {highlights.best_rs_vs_spy && (
                <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200">
                  <span className="text-zinc-400">{t.compare.bestRs}</span> {highlights.best_rs_vs_spy}
                </span>
              )}
              {highlights.best_data_quality && (
                <span className="rounded-full border border-zinc-700 bg-zinc-900 px-2 py-1 text-zinc-200">
                  <span className="text-zinc-400">{t.compare.bestQuality}</span>{" "}
                  {highlights.best_data_quality}
                </span>
              )}
            </div>
          )}

          <div className="compare-table-wrap surface-card overflow-x-auto">
            <table className="compare-table min-w-full">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-950 text-left">
                  <th className="compare-metric-label sticky left-0 z-10 bg-zinc-950 px-5 py-4">
                    {t.common.metric}
                  </th>
                  {data.entries.map((e) => (
                    <th key={e.symbol} className="min-w-[8rem] px-5 py-4 text-zinc-100">
                      <div className="flex flex-col gap-0.5">
                        <span>{e.symbol}</span>
                        <Link
                          href={`/workspace?symbol=${e.symbol}`}
                          className="text-xs font-normal text-[#7dff8e] underline"
                        >
                          {t.compare.openInWorkspace}
                        </Link>
                      </div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {METRIC_ROWS.map((row) => (
                  <tr key={row.id} className="border-b border-zinc-800/60">
                    <th
                      scope="row"
                      className="compare-metric-label sticky left-0 z-10 px-5 py-4 text-left"
                    >
                      {row.label}
                    </th>
                    {data.entries.map((entry) => {
                      const isWinner = winnersByRow[row.id] === entry.symbol;
                      return (
                        <td
                          key={`${entry.symbol}-${row.id}`}
                          className={clsx(
                            "compare-cell px-5 py-4 tabular-nums",
                            entry.error && "text-red-300",
                            isWinner && "compare-cell--best"
                          )}
                        >
                          {entry.error && row.id === "watchlistScore"
                            ? entry.error
                            : row.format(entry)}
                          {entry.stale && row.id === "watchlistScore" && (
                            <span className="compare-tag compare-tag--warn">{t.compare.tagStale}</span>
                          )}
                          {!entry.on_watchlist && row.id === "watchlistScore" && !entry.error && (
                            <span className="compare-tag">{t.compare.tagNotOnList}</span>
                          )}
                          {isWinner && !entry.error && (
                            <span className="compare-tag compare-tag--best">{t.compare.tagBest}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-3 md:grid-cols-2">
            {data.entries.map((entry) =>
              entry.summary ? (
                <div key={`sum-${entry.symbol}`} className="surface-card p-3 text-xs">
                  <p className="font-semibold text-zinc-300">{entry.symbol}</p>
                  <p className="mt-1 text-zinc-500 line-clamp-3">{entry.summary}</p>
                </div>
              ) : null
            )}
          </div>
        </>
      )}
    </div>
  );
}
