// Trade journal — manual entry, uploads, and process-quality review.
"use client";

import {
  createTradeManual,
  createTradeUpload,
  deleteTrade,
  getTradeStats,
  listTrades,
  syncTradeToPortfolio,
} from "@/lib/api";
import {
  formatDateTime,
  fromDatetimeLocalValue,
  parseApiDate,
  toDatetimeLocalValue,
} from "@/lib/datetime";
import { useTranslation, useTRef } from "@/lib/i18n";
import type { TradeCreateRequest, TradeItem, TradeStatsResponse } from "@/lib/types";
import { MetricCard } from "@/components/ui/MetricCard";
import { DenseTable } from "@/components/ui/DenseTable";
import clsx from "clsx";
import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:18731";

const defaultManual: TradeCreateRequest = {
  symbol: "",
  side: "long",
  entry_time: toDatetimeLocalValue(),
  entry_price: 0,
  setup_tags: [],
  thesis: "",
  notes: "",
};

const inputClass =
  "mt-1 w-full rounded-lg border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-[#00c805]";

function formatDate(value?: string | null): string {
  return formatDateTime(value);
}

function qualityTone(score: number): string {
  if (score >= 80) return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  if (score >= 65) return "text-lime-300 border-lime-500/40 bg-lime-500/10";
  if (score >= 50) return "text-amber-300 border-amber-500/40 bg-amber-500/10";
  return "text-red-300 border-red-500/40 bg-red-500/10";
}

function portfolioSyncBadgeClass(status: TradeItem["portfolio_sync_status"]): string {
  if (status === "synced") return "text-emerald-300 border-emerald-500/40 bg-emerald-500/10";
  if (status === "pending") return "text-amber-300 border-amber-500/40 bg-amber-500/10";
  return "text-zinc-400 border-zinc-600/50 bg-zinc-900/60";
}

type TradeSortField = "updated" | "quality" | "pnl";
type SortDirection = "asc" | "desc";

const compactInputClass =
  "h-9 w-full min-w-0 rounded-md border border-zinc-700 bg-zinc-950/80 px-2.5 text-sm text-zinc-100 outline-none focus:border-[#00c805]";

export function TradeJournal({
  embedded = false,
  compact = false,
}: {
  embedded?: boolean;
  compact?: boolean;
}) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [trades, setTrades] = useState<TradeItem[]>([]);
  const [stats, setStats] = useState<TradeStatsResponse | null>(null);
  const [manual, setManual] = useState<TradeCreateRequest>(defaultManual);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadTags, setUploadTags] = useState("");
  const [status, setStatus] = useState<string>("");
  const [statusTone, setStatusTone] = useState<"neutral" | "success" | "error">("neutral");
  const [sortField, setSortField] = useState<TradeSortField>("updated");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [syncingTradeId, setSyncingTradeId] = useState<number | null>(null);

  const reload = useCallback(async () => {
    const [rows, summary] = await Promise.all([listTrades(), getTradeStats()]);
    setTrades(rows);
    setStats(summary);
  }, []);

  useEffect(() => {
    reload().catch(() => {
      setStatusTone("error");
      setStatus(tRef.current.journal.loadFailed);
    });
  }, [reload]);

  const submitManual = async () => {
    if (!manual.symbol.trim()) {
      setStatusTone("error");
      setStatus(t.journal.symbolRequired);
      return;
    }
    if (!compact) {
      if (!manual.entry_price) {
        setStatusTone("error");
        setStatus(t.journal.entryPriceRequired);
        return;
      }
      if (!manual.quantity || manual.quantity <= 0) {
        setStatusTone("error");
        setStatus(t.journal.quantityRequired);
        return;
      }
    }
    const entryPrice = manual.entry_price && manual.entry_price > 0 ? manual.entry_price : 0;
    const exitPrice = manual.exit_price && manual.exit_price > 0 ? manual.exit_price : null;
    const quantity = manual.quantity && manual.quantity > 0 ? manual.quantity : null;
    try {
      setStatusTone("neutral");
      setStatus(t.journal.saving);
      const saved = await createTradeManual({
        ...manual,
        side: "long",
        symbol: manual.symbol.toUpperCase(),
        entry_price: entryPrice,
        exit_price: exitPrice,
        quantity,
        setup_tags: (manual.setup_tags || []).filter(Boolean),
        entry_time: fromDatetimeLocalValue(manual.entry_time).toISOString(),
        exit_time: manual.exit_time ? fromDatetimeLocalValue(manual.exit_time).toISOString() : null,
      });
      setManual(defaultManual);
      await reload();
      setStatusTone("success");
      setStatus(
        saved.portfolio_synced
          ? t.journal.savedPortfolioSynced
          : saved.portfolio_message || t.journal.savedJournalOnly
      );
    } catch (err) {
      setStatusTone("error");
      setStatus(err instanceof Error ? err.message : t.journal.saveFailed);
    }
  };

  const submitUpload = async () => {
    if (!uploadFile || !manual.symbol || !manual.entry_price) {
      setStatusTone("error");
      setStatus(t.journal.uploadRequired);
      return;
    }
    if (!manual.quantity || manual.quantity <= 0) {
      setStatusTone("error");
      setStatus(t.journal.quantityRequired);
      return;
    }
    try {
      setStatusTone("neutral");
      setStatus(t.journal.uploading);
      const form = new FormData();
      form.set("screenshot", uploadFile);
      form.set("symbol", manual.symbol.toUpperCase());
      form.set("side", manual.side);
      form.set("entry_time", fromDatetimeLocalValue(manual.entry_time).toISOString());
      form.set("entry_price", String(manual.entry_price));
      form.set("quantity", String(manual.quantity));
      if (manual.exit_time) form.set("exit_time", fromDatetimeLocalValue(manual.exit_time).toISOString());
      if (manual.exit_price != null) form.set("exit_price", String(manual.exit_price));
      if (manual.stop_loss != null) form.set("stop_loss", String(manual.stop_loss));
      if (manual.take_profit != null) form.set("take_profit", String(manual.take_profit));
      if (manual.thesis) form.set("thesis", manual.thesis);
      if (manual.notes) form.set("notes", manual.notes);
      form.set("setup_tags", uploadTags);
      const saved = await createTradeUpload(form);
      setUploadFile(null);
      setUploadTags("");
      await reload();
      setStatusTone("success");
      setStatus(
        saved.portfolio_synced
          ? t.journal.savedPortfolioSynced
          : saved.portfolio_message || t.journal.savedJournalOnly
      );
    } catch (err) {
      setStatusTone("error");
      setStatus(err instanceof Error ? err.message : t.journal.uploadFailed);
    }
  };

  const summaryFlags = useMemo(() => stats?.top_flags ?? [], [stats]);
  const sortedTrades = useMemo(() => {
    const rows = [...trades];
    rows.sort((a, b) => {
      let aVal = 0;
      let bVal = 0;
      if (sortField === "quality") {
        aVal = a.review.quality_score ?? 0;
        bVal = b.review.quality_score ?? 0;
      } else if (sortField === "pnl") {
        aVal = a.review.pnl_pct ?? Number.NEGATIVE_INFINITY;
        bVal = b.review.pnl_pct ?? Number.NEGATIVE_INFINITY;
      } else {
        aVal = parseApiDate(a.updated_at || a.created_at).getTime();
        bVal = parseApiDate(b.updated_at || b.created_at).getTime();
      }
      return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
    });
    return rows;
  }, [trades, sortField, sortDirection]);

  const recentTrades = useMemo(() => sortedTrades.slice(0, 8), [sortedTrades]);

  const syncTrade = async (trade: TradeItem) => {
    try {
      setSyncingTradeId(trade.id);
      setStatusTone("neutral");
      setStatus(t.journal.syncingPortfolio);
      const res = await syncTradeToPortfolio(trade.id);
      await reload();
      setStatusTone("success");
      setStatus(
        res.portfolio_synced
          ? t.journal.syncPortfolioDone
          : res.portfolio_message || t.journal.syncPortfolioFailed
      );
    } catch (err) {
      setStatusTone("error");
      setStatus(err instanceof Error ? err.message : t.journal.syncPortfolioFailed);
    } finally {
      setSyncingTradeId(null);
    }
  };

  const removeTrade = async (tradeId: number) => {
    try {
      await deleteTrade(tradeId);
      await reload();
      setStatusTone("success");
      setStatus(`${t.common.delete} #${tradeId}`);
    } catch (err) {
      setStatusTone("error");
      setStatus(err instanceof Error ? err.message : t.journal.saveFailed);
    }
  };

  if (compact) {
    return (
      <div className="home-journal-panel">
        <div className="home-journal-panel__header">
          <div>
            <h2 id="home-journal-title" className="data-panel-title">
              {t.home.journalTitle}
            </h2>
            <p className="data-panel-subtitle">{t.home.journalSubtitle}</p>
          </div>
        </div>

        <div className="home-journal-quick">
          <label className="home-journal-quick__field">
            <span className="home-journal-quick__label">{t.common.symbol}</span>
            <input
              value={manual.symbol}
              onChange={(e) => setManual((p) => ({ ...p, symbol: e.target.value.toUpperCase() }))}
              placeholder={t.journal.symbolPlaceholder}
              className={compactInputClass}
            />
          </label>
          <label className="home-journal-quick__field home-journal-quick__field--narrow">
            <span className="home-journal-quick__label">{t.home.journalQtyOptional}</span>
            <input
              type="number"
              step="0.01"
              min={0}
              value={manual.quantity ?? ""}
              onChange={(e) =>
                setManual((p) => ({ ...p, quantity: e.target.value ? Number(e.target.value) : null }))
              }
              className={compactInputClass}
            />
          </label>
          <label className="home-journal-quick__field home-journal-quick__field--narrow">
            <span className="home-journal-quick__label">{t.home.journalEntryOptional}</span>
            <input
              type="number"
              step="0.0001"
              min={0}
              value={manual.entry_price > 0 ? manual.entry_price : ""}
              onChange={(e) =>
                setManual((p) => ({ ...p, entry_price: e.target.value ? Number(e.target.value) : 0 }))
              }
              placeholder="—"
              className={compactInputClass}
            />
          </label>
          <label className="home-journal-quick__field home-journal-quick__field--narrow">
            <span className="home-journal-quick__label">{t.home.journalExitOptional}</span>
            <input
              type="number"
              step="0.0001"
              min={0}
              value={manual.exit_price && manual.exit_price > 0 ? manual.exit_price : ""}
              onChange={(e) =>
                setManual((p) => ({ ...p, exit_price: e.target.value ? Number(e.target.value) : null }))
              }
              placeholder="—"
              className={compactInputClass}
            />
          </label>
          <button type="button" onClick={() => void submitManual()} className="btn-primary home-journal-quick__save">
            {t.journal.saveTrade}
          </button>
        </div>

        <label className="home-journal-notes">
          <span className="home-journal-quick__label">{t.journal.notes}</span>
          <input
            value={manual.notes}
            onChange={(e) => setManual((p) => ({ ...p, notes: e.target.value }))}
            placeholder={t.home.journalNotesPlaceholder}
            className={compactInputClass}
          />
        </label>

        {status && (
          <p
            className={clsx(
              "home-journal-panel__status",
              statusTone === "success" && "home-journal-panel__status--success",
              statusTone === "error" && "home-journal-panel__status--error"
            )}
            role="status"
          >
            {status}
          </p>
        )}

        {recentTrades.length > 0 && (
          <details className="home-journal-recent">
            <summary className="home-journal-recent__summary">
              {t.home.journalRecent} ({recentTrades.length})
            </summary>
            <DenseTable caption={t.home.journalRecent} className="home-journal-recent__table">
              <thead>
                <tr>
                  <th>{t.common.symbol}</th>
                  <th className="col-num">{t.journal.entryPrice}</th>
                  <th className="col-num">{t.journal.exitPrice}</th>
                  <th>{t.home.journalRowActions}</th>
                </tr>
              </thead>
              <tbody>
                {recentTrades.map((trade) => (
                  <tr key={trade.id}>
                    <td className="font-semibold">{trade.symbol}</td>
                    <td className="col-num finance-value">
                      {trade.entry_price > 0 ? trade.entry_price.toFixed(2) : "—"}
                    </td>
                    <td className="col-num finance-value">
                      {trade.exit_price != null && trade.exit_price > 0 ? trade.exit_price.toFixed(2) : "—"}
                    </td>
                    <td>
                      <div className="flex justify-end gap-1">
                        {trade.portfolio_sync_status !== "synced" && (
                          <button
                            type="button"
                            disabled={syncingTradeId === trade.id || trade.portfolio_sync_status === "needs_quantity"}
                            onClick={() => void syncTrade(trade)}
                            className="home-journal-row-action"
                          >
                            {t.journal.syncToPortfolio}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => void removeTrade(trade.id)}
                          className="home-journal-row-action home-journal-row-action--danger"
                        >
                          {t.common.delete}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </DenseTable>
          </details>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {!embedded && (
        <div className="surface-card p-5">
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{t.journal.title}</h1>
          <p className="mt-1 text-sm text-zinc-500">{t.journal.subtitle}</p>
        </div>
      )}

      {stats && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label={t.journal.totalTrades}
            hint={t.journal.totalTradesHint}
            value={<span className="tabular-nums">{stats.total_trades}</span>}
          />
          <MetricCard
            label={t.journal.winRate}
            hint={t.journal.winRateHint}
            value={<span className="tabular-nums">{stats.win_rate_pct}%</span>}
            tone={stats.win_rate_pct >= 50 ? "ok" : "default"}
          />
          <MetricCard
            label={t.journal.avgQuality}
            hint={t.journal.avgQualityHint}
            value={<span className="tabular-nums">{stats.avg_quality_score}</span>}
          />
          <MetricCard
            label={t.journal.strongProcess}
            hint={t.journal.strongProcessHint}
            value={<span className="tabular-nums">{stats.strong_process_rate_pct}%</span>}
            tone={stats.strong_process_rate_pct >= 60 ? "ok" : "default"}
          />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="surface-card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-zinc-100">{t.journal.manualEntry}</h2>
          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-xs text-zinc-500">
              {t.common.symbol}
              <input
                value={manual.symbol}
                onChange={(e) => setManual((p) => ({ ...p, symbol: e.target.value }))}
                placeholder={t.journal.symbolPlaceholder}
                className={inputClass}
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t.journal.side}
              <select
                value={manual.side}
                onChange={(e) => setManual((p) => ({ ...p, side: e.target.value as "long" | "short" }))}
                className={inputClass}
              >
                <option value="long">{t.journal.long}</option>
                <option value="short">{t.journal.short}</option>
              </select>
            </label>
            <label className="text-xs text-zinc-500">
              {t.journal.sleeve}
              <select
                value={manual.sleeve ?? ""}
                onChange={(e) =>
                  setManual((p) => ({
                    ...p,
                    sleeve: (e.target.value || undefined) as TradeCreateRequest["sleeve"],
                  }))
                }
                className={inputClass}
              >
                <option value="">{t.buckets.autoDetect}</option>
                <option value="penny">{t.buckets.penny.label}</option>
                <option value="medium">{t.buckets.medium.label}</option>
                <option value="compounder">{t.buckets.compounder.label}</option>
              </select>
            </label>
          </div>
          <label className="text-xs text-zinc-500">
            {t.journal.entryTime}
            <input
              type="datetime-local"
              value={manual.entry_time}
              onChange={(e) => setManual((p) => ({ ...p, entry_time: e.target.value }))}
              className={inputClass}
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-zinc-500">
              {t.journal.entryPrice}
              <input
                type="number"
                step="0.0001"
                placeholder="0.00"
                value={manual.entry_price || ""}
                onChange={(e) => setManual((p) => ({ ...p, entry_price: Number(e.target.value) }))}
                className={inputClass}
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t.journal.exitPrice}
              <input
                type="number"
                step="0.0001"
                placeholder="0.00"
                value={manual.exit_price ?? ""}
                onChange={(e) =>
                  setManual((p) => ({ ...p, exit_price: e.target.value ? Number(e.target.value) : null }))
                }
                className={inputClass}
              />
            </label>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-xs text-zinc-500">
              {t.journal.quantity}
              <input
                type="number"
                step="0.01"
                min={0}
                required
                placeholder="0"
                value={manual.quantity ?? ""}
                onChange={(e) =>
                  setManual((p) => ({ ...p, quantity: e.target.value ? Number(e.target.value) : null }))
                }
                className={inputClass}
              />
              <span className="mt-1 block text-sm text-zinc-600">{t.journal.quantityPortfolioHint}</span>
            </label>
            <label className="text-xs text-zinc-500">
              {t.journal.stopLoss}
              <input
                type="number"
                step="0.0001"
                placeholder="0.00"
                value={manual.stop_loss ?? ""}
                onChange={(e) =>
                  setManual((p) => ({ ...p, stop_loss: e.target.value ? Number(e.target.value) : null }))
                }
                className={inputClass}
              />
            </label>
            <label className="text-xs text-zinc-500">
              {t.journal.takeProfit}
              <input
                type="number"
                step="0.0001"
                placeholder="0.00"
                value={manual.take_profit ?? ""}
                onChange={(e) =>
                  setManual((p) => ({ ...p, take_profit: e.target.value ? Number(e.target.value) : null }))
                }
                className={inputClass}
              />
            </label>
          </div>
          <label className="text-xs text-zinc-500">
            {t.journal.tags}
            <input
              placeholder="breakout, earnings, pullback"
              value={(manual.setup_tags || []).join(", ")}
              onChange={(e) =>
                setManual((p) => ({
                  ...p,
                  setup_tags: e.target.value
                    .split(",")
                    .map((x) => x.trim())
                    .filter(Boolean),
                }))
              }
              className={inputClass}
            />
          </label>
          <label className="text-xs text-zinc-500">
            {t.journal.thesis}
            <textarea
              placeholder={t.journal.thesisPlaceholder}
              value={manual.thesis}
              onChange={(e) => setManual((p) => ({ ...p, thesis: e.target.value }))}
              className={`${inputClass} h-24 resize-y`}
            />
          </label>
          <label className="text-xs text-zinc-500">
            {t.journal.notes}
            <textarea
              placeholder={t.journal.notesPlaceholder}
              value={manual.notes}
              onChange={(e) => setManual((p) => ({ ...p, notes: e.target.value }))}
              className={`${inputClass} h-24 resize-y`}
            />
          </label>
          <button type="button" onClick={submitManual} className="btn-primary px-4 py-2 text-sm sm:w-fit">
            {t.journal.saveTrade}
          </button>
        </div>

        <div className="surface-card space-y-3 p-4">
          <h2 className="text-sm font-semibold text-zinc-100">{t.journal.screenshotSection}</h2>
          <p className="text-xs text-zinc-500">{t.journal.screenshotHint}</p>
          <label className="text-xs text-zinc-500">
            {t.journal.screenshotFile}
            <input
              type="file"
              accept="image/*"
              onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              className={inputClass}
            />
          </label>
          <label className="text-xs text-zinc-500">
            {t.journal.tagOverride}
            <input
              value={uploadTags}
              onChange={(e) => setUploadTags(e.target.value)}
              placeholder="breakout, overtrade"
              className={inputClass}
            />
          </label>
          <button type="button" onClick={submitUpload} className="btn-ghost px-4 py-2 text-sm sm:w-fit">
            {t.journal.saveWithScreenshot}
          </button>
          {summaryFlags.length > 0 && (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-3 text-xs text-zinc-400">
              <p className="font-medium text-zinc-300">{t.journal.frequentIssues}</p>
              <p className="mt-1">{summaryFlags.map((f) => `${f.flag} (${f.count})`).join(" • ")}</p>
            </div>
          )}
        </div>
      </div>

      {status && (
        <p
          className={`rounded-lg border px-3 py-2 text-xs ${
            statusTone === "success"
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
              : statusTone === "error"
                ? "border-red-500/40 bg-red-500/10 text-red-300"
                : "border-zinc-700 bg-zinc-900/60 text-zinc-400"
          }`}
        >
          {status}
        </p>
      )}

      <div className="surface-card space-y-3 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-zinc-100">{t.journal.savedTrades}</h2>
          <div className="flex items-center gap-2 text-xs">
            <label className="text-zinc-500">
              <select
                value={sortField}
                onChange={(e) => setSortField(e.target.value as TradeSortField)}
                className="ml-2 rounded-lg border border-zinc-700 bg-zinc-950/80 px-2 py-1 text-zinc-200 outline-none focus:border-[#00c805]"
              >
                <option value="updated">{t.journal.sortRecent}</option>
                <option value="quality">{t.journal.sortQuality}</option>
                <option value="pnl">{t.journal.sortPnl}</option>
              </select>
            </label>
            <button
              type="button"
              onClick={() => setSortDirection((d) => (d === "asc" ? "desc" : "asc"))}
              className="btn-ghost px-2 py-1 text-xs hover:bg-zinc-900"
            >
              {sortDirection === "desc" ? t.journal.sortDesc : t.journal.sortAsc}
            </button>
          </div>
        </div>
        {trades.length === 0 ? (
          <p className="text-xs text-zinc-500">{t.journal.noTrades}</p>
        ) : (
          <div className="space-y-3">
            {sortedTrades.map((trade) => (
              <div
                key={trade.id}
                className="rounded-xl border border-zinc-800 bg-zinc-950/40 p-4 text-sm text-zinc-300"
              >
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <p className="font-semibold text-zinc-100">
                      {trade.symbol} · {trade.side.toUpperCase()}
                    </p>
                    <span
                      className={`rounded-full border px-2 py-0.5 text-xs ${qualityTone(trade.review.quality_score)}`}
                    >
                      {t.journal.quality} {trade.review.quality_score} ({trade.review.quality_label})
                    </span>
                    {syncingTradeId === trade.id ? (
                      <span className="rounded-full border border-zinc-600/50 bg-zinc-900/60 px-2 py-0.5 text-xs text-zinc-400">
                        {t.journal.syncingPortfolio}
                      </span>
                    ) : trade.portfolio_sync_status ? (
                      <span
                        className={`rounded-full border px-2 py-0.5 text-xs ${portfolioSyncBadgeClass(trade.portfolio_sync_status)}`}
                        title={trade.portfolio_sync_status === "pending" ? t.journal.syncPendingHint : undefined}
                      >
                        {trade.portfolio_sync_status === "synced"
                          ? t.journal.syncBadgeSynced
                          : trade.portfolio_sync_status === "pending"
                            ? t.journal.syncBadgePending
                            : t.journal.syncBadgeNeedsQuantity}
                      </span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={syncingTradeId === trade.id || trade.portfolio_sync_status === "needs_quantity"}
                      onClick={async () => {
                        try {
                          setSyncingTradeId(trade.id);
                          setStatusTone("neutral");
                          setStatus(t.journal.syncingPortfolio);
                          const res = await syncTradeToPortfolio(trade.id);
                          await reload();
                          setStatusTone("success");
                          setStatus(
                            res.portfolio_synced
                              ? t.journal.syncPortfolioDone
                              : res.portfolio_message || t.journal.syncPortfolioFailed
                          );
                        } catch (err) {
                          setStatusTone("error");
                          setStatus(err instanceof Error ? err.message : t.journal.syncPortfolioFailed);
                        } finally {
                          setSyncingTradeId(null);
                        }
                      }}
                      className="btn-ghost px-2 py-1 text-xs hover:bg-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t.journal.syncToPortfolio}
                    </button>
                    <button
                      type="button"
                      onClick={async () => {
                        try {
                          await deleteTrade(trade.id);
                          await reload();
                          setStatusTone("success");
                          setStatus(`${t.common.delete} #${trade.id}`);
                        } catch (err) {
                          setStatusTone("error");
                          setStatus(err instanceof Error ? err.message : t.journal.saveFailed);
                        }
                      }}
                      className="btn-ghost px-2 py-1 text-xs hover:bg-zinc-900"
                    >
                    {t.common.delete}
                  </button>
                  </div>
                </div>
                <p className="mt-2 text-xs text-zinc-400">{trade.review.review_note}</p>
                <div className="mt-3 grid gap-2 text-xs text-zinc-500 sm:grid-cols-2 lg:grid-cols-4">
                  <p>
                    {t.journal.entry}: ${trade.entry_price.toFixed(2)}
                  </p>
                  <p>
                    {t.journal.exit}:{" "}
                    {trade.exit_price != null ? `$${trade.exit_price.toFixed(2)}` : t.journal.open}
                  </p>
                  <p>
                    {t.journal.pnl}:{" "}
                    {typeof trade.review.pnl_pct === "number" ? `${trade.review.pnl_pct.toFixed(2)}%` : "—"}
                  </p>
                  <p>
                    {t.journal.entryTimeLabel}: {formatDate(trade.entry_time)}
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {trade.setup_tags.map((tag) => (
                    <span key={tag} className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
                      {tag}
                    </span>
                  ))}
                  {(trade.review.image_tags || []).map((tag) => (
                    <span
                      key={`img-${tag}`}
                      className="rounded-full border border-emerald-700/50 px-2 py-0.5 text-xs text-emerald-300"
                    >
                      img:{tag}
                    </span>
                  ))}
                  {trade.screenshot_path && (
                    <a
                      href={`${API_URL}/trades/${trade.id}/screenshot`}
                      target="_blank"
                      rel="noreferrer"
                      className="rounded-full border border-zinc-700 px-2 py-0.5 text-xs text-zinc-300 underline"
                    >
                      {t.journal.openScreenshot}
                    </a>
                  )}
                </div>
                {trade.review.image_insight && (
                  <p className="mt-2 text-xs text-zinc-500">
                    {t.journal.imageInsight} {trade.review.image_insight}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
