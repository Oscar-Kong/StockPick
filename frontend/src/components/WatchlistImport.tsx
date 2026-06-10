// Import and manual-entry workflow for adding symbols to the watchlist.
"use client";

import { addToWatchlist, importWatchlist } from "@/lib/api";
import type { Bucket, WatchlistImportRow } from "@/lib/types";
import { fmt, useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { useState } from "react";
import { ResearchReport } from "./ResearchReport";

interface WatchlistImportProps {
  onImported: () => void;
}

export function WatchlistImport({ onImported }: WatchlistImportProps) {
  const { t } = useTranslation();
  const [manualSymbol, setManualSymbol] = useState("");
  const [manualBucket, setManualBucket] = useState<Bucket>("penny");
  const [manualNotes, setManualNotes] = useState("");
  const [manualAdding, setManualAdding] = useState(false);
  const [manualMsg, setManualMsg] = useState<string | null>(null);

  const [input, setInput] = useState("");
  const [bucket, setBucket] = useState<Bucket | "auto">("auto");
  const [notes, setNotes] = useState("");
  const [scanning, setScanning] = useState(false);
  const [lastResults, setLastResults] = useState<WatchlistImportRow[] | null>(null);
  const [expandedReport, setExpandedReport] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    setScanning(true);
    setError(null);
    setLastResults(null);
    setExpandedReport(null);

    try {
      const res = await importWatchlist({ input, bucket, notes });
      setLastResults(res.results);
      onImported();
    } catch (err) {
      setError(err instanceof Error ? err.message : t.watchlist.importFailed);
    } finally {
      setScanning(false);
    }
  };

  const handleQuickAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const symbol = manualSymbol.trim().toUpperCase();
    if (!symbol) return;

    setManualAdding(true);
    setManualMsg(null);
    try {
      await addToWatchlist(symbol, manualBucket, manualNotes.trim());
      setManualMsg(fmt(t.watchlist.added, { symbol }));
      setManualSymbol("");
      onImported();
    } catch (err) {
      setManualMsg(err instanceof Error ? err.message : t.watchlist.quickAddFailed);
    } finally {
      setManualAdding(false);
    }
  };

  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <h2 className="text-sm font-semibold">{t.watchlist.toolsTitle}</h2>
      <p className="mt-1 text-xs text-zinc-500">{t.watchlist.toolsHint}</p>

      <form onSubmit={handleQuickAdd} className="mt-4 space-y-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="block text-xs text-zinc-500">
            {t.common.symbol}
            <input
              type="text"
              value={manualSymbol}
              onChange={(e) => setManualSymbol(e.target.value)}
              placeholder="AAPL"
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm uppercase dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>

          <label className="block text-xs text-zinc-500">
            {t.common.bucket}
            <select
              value={manualBucket}
              onChange={(e) => setManualBucket(e.target.value as Bucket)}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="penny">{t.buckets.penny.label}</option>
              <option value="compounder">{t.buckets.compounder.label}</option>
            </select>
          </label>

          <label className="block text-xs text-zinc-500">
            {t.common.notesOptional}
            <input
              type="text"
              value={manualNotes}
              onChange={(e) => setManualNotes(e.target.value)}
              placeholder={t.watchlist.notesPlaceholder}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={manualAdding || !manualSymbol.trim()}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {manualAdding ? t.common.adding : t.watchlist.quickAdd}
        </button>

        {manualMsg && <p className="text-sm text-zinc-500">{manualMsg}</p>}
      </form>

      <form onSubmit={handleSubmit} className="mt-4 space-y-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-800">
        <h3 className="text-sm font-semibold">{t.watchlist.importTitle}</h3>
        <label className="block text-xs text-zinc-500">
          {t.watchlist.tickers}
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={4}
            placeholder={t.watchlist.tickersPlaceholder}
            className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 font-mono text-sm dark:border-zinc-700 dark:bg-zinc-900"
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-xs text-zinc-500">
            {t.common.bucket}
            <select
              value={bucket}
              onChange={(e) => setBucket(e.target.value as Bucket | "auto")}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            >
              <option value="auto">{t.buckets.autoDetect}</option>
              <option value="penny">{t.buckets.penny.label}</option>
              <option value="compounder">{t.buckets.compounder.label}</option>
            </select>
          </label>

          <label className="block text-xs text-zinc-500">
            {t.common.notesOptional}
            <input
              type="text"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t.watchlist.notesPlaceholderImport}
              className="mt-1 w-full rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
            />
          </label>
        </div>

        <button
          type="submit"
          disabled={scanning || !input.trim()}
          className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900"
        >
          {scanning ? t.common.scanning : t.watchlist.scanAndAdd}
        </button>
      </form>

      {error && <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>}

      {lastResults && lastResults.length > 0 && (
        <div className="mt-4 space-y-3 rounded-lg border border-zinc-100 bg-zinc-50 p-3 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          <p className="font-medium">
            {fmt(t.watchlist.addedCount, {
              added: lastResults.filter((r) => r.added).length,
              total: lastResults.length,
            })}
          </p>
          <ul className="space-y-2">
            {lastResults.map((r) => (
              <li key={r.symbol} className="rounded-lg border border-zinc-200 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-950">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span>
                    {r.added ? "✓" : "✗"}{" "}
                    <span className="font-semibold">{r.symbol}</span>
                    {r.added && r.score != null && (
                      <span>
                        {" "}
                        — {t.common.score} {r.score.toFixed(1)}
                      </span>
                    )}
                    {!r.added && r.error && (
                      <span className="text-red-500"> — {r.error}</span>
                    )}
                  </span>
                  {r.added && r.report && (
                    <button
                      type="button"
                      onClick={() =>
                        setExpandedReport(expandedReport === r.symbol ? null : r.symbol)
                      }
                      className="underline"
                    >
                      {expandedReport === r.symbol ? t.watchlist.hideReport : t.watchlist.viewReport}
                    </button>
                  )}
                  {r.added && (
                    <Link
                      href={`/workspace?symbol=${r.symbol}`}
                      className="underline text-zinc-600 dark:text-zinc-400"
                    >
                      {t.watchlist.openInAnalyze}
                    </Link>
                  )}
                </div>
                {expandedReport === r.symbol && r.report && (
                  <div className="mt-3 max-h-96 overflow-y-auto border-t border-zinc-100 pt-3 dark:border-zinc-800">
                    <ResearchReport report={r.report} />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
