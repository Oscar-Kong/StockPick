// Shared bucket page workflow for running scans and exploring results.
"use client";

import {
  addToWatchlist,
  deleteSavedScan,
  getLatestScan,
  getScanStatus,
  listSavedScans,
  saveScanSnapshot,
  startScan,
} from "@/lib/api";
import { getBucketMeta } from "@/lib/buckets";
import { fmt, useTranslation } from "@/lib/i18n";
import type { Bucket, SavedScanItem, ScanOptions, ScanParitySummary, StockResult } from "@/lib/types";
import { formatDateTime } from "@/lib/datetime";
import { isStaleTimestamp } from "@/lib/quantHealth";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ScanControls } from "./ScanControls";
import { ScanProgress } from "./ScanProgress";
import { ScanScoreMeta } from "./ScanScoreMeta";
import { StaleDataBadge } from "./badges/StaleDataBadge";
import { StockDetailDrawer } from "./StockDetailDrawer";
import { StockTable } from "./StockTable";
import { StrategyVersionBadge } from "./DataQualityBadge";

interface BucketPageProps {
  bucket: Bucket;
  title?: string;
  description?: string;
  /** When true, parent page renders the main heading and bucket tabs. */
  embedded?: boolean;
}

export function BucketPage({ bucket, title, description, embedded }: BucketPageProps) {
  const { t } = useTranslation();
  const meta = getBucketMeta(t)[bucket];
  const displayTitle = title ?? meta.title;
  const displayDescription = description ?? meta.description;

  const searchParams = useSearchParams();
  const defaultOptions: ScanOptions = { max_results: 25 };
  const [options, setOptions] = useState<ScanOptions>({ max_results: 25 });
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState<StockResult[]>([]);
  const [selected, setSelected] = useState<StockResult | null>(null);
  const [lastScanAt, setLastScanAt] = useState<string | null>(null);
  const [strategyVersion, setStrategyVersion] = useState<string | null>(null);
  const [scoringEngineUsed, setScoringEngineUsed] = useState<boolean | null>(null);
  const [paritySummary, setParitySummary] = useState<ScanParitySummary | null>(null);
  const [savedScans, setSavedScans] = useState<SavedScanItem[]>([]);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [saveMsgSuccess, setSaveMsgSuccess] = useState(false);
  const [savingScan, setSavingScan] = useState(false);
  const [watchlistAdded, setWatchlistAdded] = useState<Set<string>>(() => new Set());
  const [watchlistPending, setWatchlistPending] = useState<string | null>(null);
  const latestScanLoadedRef = useRef(false);
  const presetLoadedRef = useRef(false);

  const loadSavedScans = useCallback(async () => {
    try {
      const rows = await listSavedScans(bucket);
      setSavedScans(rows);
    } catch {
      setSavedScans([]);
    }
  }, [bucket]);

  const loadLatestScan = useCallback(async () => {
    try {
      const data = await getLatestScan(bucket);
      setResults(data.results);
      setLastScanAt(data.completed_at);
      setStrategyVersion(data.strategy_version ?? null);
      setScoringEngineUsed(data.scoring_engine_used ?? null);
      setParitySummary(data.parity_summary ?? null);
      setStatus("completed");
      setMessage(fmt(t.scan.loadedResults, { count: data.results.length }));
    } catch {
      setMessage(t.scan.noLatestScan);
    }
  }, [bucket, t]);

  useEffect(() => {
    if (latestScanLoadedRef.current) return;
    latestScanLoadedRef.current = true;
    loadLatestScan();
  }, [loadLatestScan]);

  useEffect(() => {
    if (presetLoadedRef.current) return;
    const scopedBucket = searchParams.get("bucket");
    if (scopedBucket && scopedBucket !== bucket) return;
    const next: ScanOptions = { ...options };
    const maxResults = searchParams.get("max_results");
    const minPrice = searchParams.get("min_price");
    const maxPrice = searchParams.get("max_price");
    const minVolume = searchParams.get("min_volume");
    if (maxResults) next.max_results = Number(maxResults);
    if (minPrice) next.min_price = Number(minPrice);
    if (maxPrice) next.max_price = Number(maxPrice);
    if (minVolume) next.min_volume = Number(minVolume);
    const hasPreset = Boolean(maxResults || minPrice || maxPrice || minVolume);
    if (hasPreset) {
      setOptions(next);
      setMessage(t.scan.presetLoaded);
      presetLoadedRef.current = true;
    }
  }, [bucket, options, searchParams, t]);

  useEffect(() => {
    void loadSavedScans();
  }, [loadSavedScans]);

  const pollScan = useCallback(async (jobId: string) => {
    let ticks = 0;
    const interval = setInterval(async () => {
      ticks += 1;
      try {
        const data = await getScanStatus(jobId);
        setProgress(data.progress);
        setMessage(data.message);
        setStatus(data.status);
        if (data.status === "completed") {
          setResults(data.results);
          setLastScanAt(data.completed_at ?? new Date().toISOString());
          setScoringEngineUsed(data.scoring_engine_used ?? null);
          setParitySummary(data.parity_summary ?? null);
          setScanning(false);
          clearInterval(interval);
        } else if (data.status === "failed") {
          setScanning(false);
          clearInterval(interval);
        } else if (ticks >= 120) {
          setScanning(false);
          setStatus("failed");
          setMessage(t.scan.scanTimeout);
          clearInterval(interval);
        }
      } catch {
        setScanning(false);
        setStatus("failed");
        setMessage(t.scan.statusFetchFailed);
        clearInterval(interval);
      }
    }, 1500);
  }, [t]);

  const handleScan = async () => {
    setScanning(true);
    setStatus("running");
    setProgress(0);
    setMessage(t.scan.startingScan);
    setSelected(null);
    setScoringEngineUsed(null);
    setParitySummary(null);
    try {
      const job = await startScan(bucket, options);
      await pollScan(job.job_id);
    } catch (err) {
      setScanning(false);
      setStatus("failed");
      setMessage(err instanceof Error ? err.message : t.scan.scanFailed);
    }
  };

  const resetFilters = () => {
    setOptions(defaultOptions);
    setMessage(t.scan.filtersReset);
  };

  const scanStale = isStaleTimestamp(lastScanAt, 24 * 60 * 60 * 1000);

  const handleWatchlist = async (stock: StockResult) => {
    const sym = stock.symbol.toUpperCase();
    if (watchlistAdded.has(sym)) return;
    setWatchlistPending(sym);
    setSaveMsg(null);
    try {
      await addToWatchlist(sym, bucket, stock.summary.slice(0, 200));
      setWatchlistAdded((prev) => new Set(prev).add(sym));
      setSaveMsg(fmt(t.scan.watchlistAdded, { symbol: sym }));
      setSaveMsgSuccess(true);
    } catch (err) {
      setSaveMsg(
        err instanceof Error
          ? err.message
          : fmt(t.scan.watchlistAddFailed, { symbol: sym })
      );
      setSaveMsgSuccess(false);
    } finally {
      setWatchlistPending(null);
    }
  };

  const handleSaveCurrentScan = async () => {
    if (results.length === 0) return;
    setSavingScan(true);
    setSaveMsg(null);
    try {
      await saveScanSnapshot({
        bucket,
        options: options as Record<string, unknown>,
        results,
        strategy_version: strategyVersion,
        completed_at: lastScanAt,
      });
      setSaveMsg(t.scan.scanSaved);
      setSaveMsgSuccess(true);
      await loadSavedScans();
    } catch (err) {
      setSaveMsg(err instanceof Error ? err.message : t.scan.saveScanFailed);
      setSaveMsgSuccess(false);
    } finally {
      setSavingScan(false);
    }
  };

  const handleLoadSavedScan = (row: SavedScanItem) => {
    setResults(row.results);
    setLastScanAt(row.completed_at ?? row.created_at);
    setStrategyVersion(row.strategy_version ?? null);
    setScoringEngineUsed(null);
    setParitySummary(null);
    setStatus("completed");
    setMessage(fmt(t.scan.loadedSavedScan, { name: row.name }));
  };

  const handleDeleteSavedScan = async (scanId: number) => {
    await deleteSavedScan(scanId);
    await loadSavedScans();
  };

  return (
    <div className="space-y-6">
      {!embedded && (
        <div className="surface-card p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-zinc-100">{displayTitle}</h1>
              <p className="mt-1 text-sm text-zinc-500">{displayDescription}</p>
              <p className="mt-1 text-xs text-zinc-500">{t.scan.workflow}</p>
            </div>
            <div className="chip px-3 py-2 text-xs text-zinc-300">
              {fmt(t.scan.bucketChip, { bucket: meta.label })}
            </div>
          </div>
        </div>
      )}

      <ScanControls
        bucketLabel={displayTitle}
        options={options}
        onChange={setOptions}
        onScan={handleScan}
        onReset={resetFilters}
        scanning={scanning}
      />
      <div className="surface-card flex flex-wrap items-center gap-2 px-3 py-2 text-xs text-zinc-500">
        {lastScanAt && (
          <span className="chip px-2 py-1">
            {t.scan.lastScan} {formatDateTime(lastScanAt)}
          </span>
        )}
        <StrategyVersionBadge version={strategyVersion} />
        <ScanScoreMeta
          scoringEngineUsed={scoringEngineUsed}
          paritySummary={paritySummary}
        />
        {scanStale && lastScanAt && <StaleDataBadge asOf={lastScanAt} />}
        <button
          type="button"
          onClick={loadLatestScan}
          className="btn-ghost px-2 py-1 hover:bg-zinc-900/70"
        >
          {t.scan.loadLastScan}
        </button>
        <button
          type="button"
          onClick={handleSaveCurrentScan}
          disabled={savingScan || results.length === 0}
          className="btn-ghost px-2 py-1 hover:bg-zinc-900/70"
        >
          {savingScan ? t.common.saving : t.scan.saveSnapshot}
        </button>
        {(bucket === "penny" || bucket === "medium") && (
          <span className="text-amber-600 dark:text-amber-400">{t.scan.rescanHint}</span>
        )}
      </div>
      {saveMsg && (
        <p
          className={
            saveMsgSuccess ? "text-xs text-[#7dff8e]" : "text-xs text-amber-400"
          }
        >
          {saveMsg}
        </p>
      )}

      {savedScans.length > 0 && (
        <div className="surface-card space-y-2 px-3 py-2">
          <p className="text-xs font-medium text-zinc-400">{t.scan.savedScans}</p>
          <div className="flex flex-wrap gap-2">
            {savedScans.slice(0, 8).map((s) => (
              <div key={s.id} className="flex items-center gap-1 rounded-lg border border-zinc-800 px-2 py-1 text-xs">
                <button type="button" onClick={() => handleLoadSavedScan(s)} className="underline">
                  {s.name} ({s.result_count})
                </button>
                <button type="button" onClick={() => handleDeleteSavedScan(s.id)} className="text-zinc-500">
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {(scanning || status === "running") && (
        <ScanProgress progress={progress} message={message} status={status} />
      )}

      <StockTable
        results={results}
        onSelect={setSelected}
        onAddWatchlist={handleWatchlist}
        watchlistAdded={watchlistAdded}
        watchlistPending={watchlistPending}
        scoringEngineUsed={scoringEngineUsed}
      />

      <StockDetailDrawer
        stock={selected}
        bucket={bucket}
        scoringEngineUsed={scoringEngineUsed}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}
