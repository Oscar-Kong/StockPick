"use client";

import { getScanPickSummary } from "@/lib/api";
import { useTranslation, useTRef } from "@/lib/i18n";
import type { ScanPickSummaryResponse, StockResult } from "@/lib/types";
import clsx from "clsx";
import { useCallback, useEffect, useRef, useState } from "react";

interface ScanPickSummaryCellProps {
  stock: StockResult;
  variant?: "table" | "drawer";
}

function blurb(stock: StockResult): string {
  const m = stock.metrics ?? {};
  const line = (m.business_line as string) || (m.theme_module as string) || stock.summary;
  if (!line) return stock.symbol;
  return line.length > 72 ? `${line.slice(0, 71)}…` : line;
}

export function ScanPickSummaryCell({ stock, variant = "table" }: ScanPickSummaryCellProps) {
  const { locale, t } = useTranslation();
  const tRef = useTRef();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ScanPickSummaryResponse | null>(null);
  const fetchedLocaleRef = useRef<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    if (data && fetchedLocaleRef.current === locale) {
      setOpen(true);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await getScanPickSummary(stock.bucket, stock, locale);
      setData(res);
      fetchedLocaleRef.current = locale;
      setOpen(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : tRef.current.scan.summaryUnavailable);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  }, [data, stock, locale, tRef]);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const isDrawer = variant === "drawer";

  return (
    <div ref={panelRef} className={clsx("relative", isDrawer && "space-y-2")}>
      {!isDrawer && (
        <p className="mb-1.5 line-clamp-1 text-[11px] leading-snug text-zinc-500">{blurb(stock)}</p>
      )}
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          void load();
        }}
        disabled={loading}
        className={clsx(
          "inline-flex items-center gap-1 rounded-md border text-xs font-medium transition",
          isDrawer
            ? "border-zinc-700 bg-zinc-900 px-3 py-1.5 text-zinc-200 hover:border-[#00c805]/40 hover:bg-[#00c805]/10"
            : "border-zinc-700/80 bg-zinc-950 px-2 py-1 text-zinc-300 hover:border-[#00c805]/50 hover:text-[#7dff8e]",
          loading && "opacity-60"
        )}
      >
        {loading ? "…" : t.scan.summary}
        {data?.source === "llm" && !loading && (
          <span className="rounded bg-[#00c805]/15 px-1 text-[9px] uppercase tracking-wide text-[#7dff8e]">
            AI
          </span>
        )}
      </button>

      {open && (
        <div
          className={clsx(
            "z-20 rounded-lg border border-zinc-700 bg-zinc-950 p-3 shadow-xl",
            isDrawer ? "mt-2 w-full" : "absolute right-0 top-full mt-1 w-[min(320px,85vw)]"
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-zinc-200">
              {stock.symbol} · {t.scan.scanNote}
            </span>
            <button
              type="button"
              className="text-xs text-zinc-500 hover:text-zinc-300"
              onClick={() => setOpen(false)}
            >
              {t.scan.close}
            </button>
          </div>
          {error && <p className="text-xs text-red-400">{error}</p>}
          {data && !error && (
            <div className="space-y-2.5 text-xs leading-relaxed text-zinc-400">
              <div>
                <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  {t.scan.background}
                </p>
                <p>{data.background}</p>
              </div>
              <div>
                <p className="mb-0.5 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  {t.scan.whyRanked}
                </p>
                <p>{data.why_picked}</p>
              </div>
            </div>
          )}
          <p className="mt-2 text-[10px] text-zinc-600">{t.scan.disclaimer}</p>
        </div>
      )}
    </div>
  );
}
