// Shared bucket page workflow for running scans and exploring results.
"use client";

import {
  addToWatchlist,
  deleteSavedScan,
  getDailyDashboard,
  getLatestScan,
  listSavedScans,
  saveScanSnapshot,
  startScan,
} from "@/lib/api";
import { getBucketMeta } from "@/lib/buckets";
import { formatDateTime } from "@/lib/datetime";
import { fmt, useTranslation, useTRef } from "@/lib/i18n";
import type {
  Bucket,
  HeldPositionSummary,
  SavedScanItem,
  ScanOptions,
  ScanParitySummary,
  StockResult,
} from "@/lib/types";
import { isStaleTimestamp } from "@/lib/quantHealth";
import { startScanPoll } from "@/lib/scanPoll";
import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ScanScoringNote } from "./product/ScanScoringNote";
import { countAdvancedFilters, ScanCommandBar } from "./scan/ScanCommandBar";
import { ScanInlineStatus, ScanProgressBar } from "./scan/ScanInlineStatus";
import { SavedScansMenu } from "./scan/SavedScansMenu";
import { StockTable } from "./StockTable";
import { StaleDataBadge } from "./badges/StaleDataBadge";
import clsx from "clsx";

interface BucketPageProps {
  bucket: Bucket;
  title?: string;
  description?: string;
  embedded?: boolean;
  onMetaChange?: (meta: ScanPageMeta) => void;
}

export interface ScanPageMeta {
  bucket: Bucket;
  bucketLabel: string;
  description: string;
  lastScanAt: string | null;
  scanStale: boolean;
  resultCount: number;
}

export function BucketPage({ bucket, title, description, embedded, onMetaChange }: BucketPageProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const meta = getBucketMeta(t)[bucket];
  const displayTitle = title ?? meta.title;
  const displayDescription = description ?? meta.description;

  const searchParams = useSearchParams();
  const defaultOptions: ScanOptions = { max_results: 50, mode: "fast" };
  const [options, setOptions] = useState<ScanOptions>(defaultOptions);
  const [scanning, setScanning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState("idle");
  const [results, setResults] = useState<StockResult[]>([]);
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
  const [heldPositions, setHeldPositions] = useState<Map<string, HeldPositionSummary>>(() => new Map());
  const latestScanLoadedRef = useRef(false);
  const presetLoadedRef = useRef(false);
  const pollRef = useRef<(() => void) | null>(null);

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      pollRef.current();
      pollRef.current = null;
    }
  }, []);

  useEffect(() => clearPoll, [clearPoll]);

  const scanStale = isStaleTimestamp(lastScanAt, 24 * 60 * 60 * 1000);

  useEffect(() => {
    onMetaChange?.({
      bucket,
      bucketLabel: meta.label,
      description: displayDescription,
      lastScanAt,
      scanStale,
      resultCount: results.length,
    });
  }, [bucket, meta.label, displayDescription, lastScanAt, scanStale, results.length, onMetaChange]);

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
      setMessage(fmt(tRef.current.scan.loadedResults, { count: data.results.length }));
    } catch {
      setMessage(tRef.current.scan.noLatestScan);
    }
  }, [bucket, tRef]);

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
      setMessage(tRef.current.scan.presetLoaded);
      presetLoadedRef.current = true;
    }
  }, [bucket, options, searchParams, tRef]);

  useEffect(() => {
    void loadSavedScans();
  }, [loadSavedScans]);

  useEffect(() => {
    void getDailyDashboard({ skipAutoRefresh: true })
      .then((data) => {
        const map = new Map<string, HeldPositionSummary>();
        for (const h of data.holdings) {
          if (h.shares > 0) {
            map.set(h.symbol.toUpperCase(), { shares: h.shares, avgCost: h.avg_cost });
          }
        }
        setHeldPositions(map);
      })
      .catch(() => setHeldPositions(new Map()));
  }, []);

  const pollScan = useCallback(
    (jobId: string) => {
      clearPoll();
      const stop = startScanPoll(jobId, {
        onUpdate: (data) => {
          setProgress(data.progress);
          setMessage(data.message);
          setStatus(data.status);
        },
        onComplete: (data) => {
          setResults(data.results);
          setLastScanAt(data.completed_at ?? new Date().toISOString());
          setScoringEngineUsed(data.scoring_engine_used ?? null);
          setParitySummary(data.parity_summary ?? null);
          setScanning(false);
          setStatus("completed");
        },
        onFailed: (reason) => {
          setScanning(false);
          setStatus("failed");
          setMessage(reason);
        },
      });
      pollRef.current = stop;
    },
    [clearPoll]
  );

  const handleScan = async () => {
    setScanning(true);
    setStatus("running");
    setProgress(0);
    setMessage(t.scan.startingScan);
    setScoringEngineUsed(null);
    setParitySummary(null);
    try {
      const job = await startScan(bucket, options);
      pollScan(job.job_id);
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
      setSaveMsg(err instanceof Error ? err.message : fmt(t.scan.watchlistAddFailed, { symbol: sym }));
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

  const advancedCount = countAdvancedFilters(options);

  return (
    <div className="scan-workspace flex min-h-0 flex-1 flex-col gap-2">
      {!embedded && (
        <header className="scan-page-header">
          <div>
            <h1 className="scan-page-header__title">{displayTitle}</h1>
            <p className="scan-page-header__desc">{displayDescription}</p>
          </div>
          <div className="scan-page-header__meta">
            <span className="chip px-2 py-0.5 text-sm">{meta.label}</span>
            {lastScanAt && (
              <span className="text-sm text-secondary">
                {t.scan.lastScanLabel} {formatDateTime(lastScanAt)}
              </span>
            )}
            {lastScanAt &&
              (scanStale ? <StaleDataBadge asOf={lastScanAt} /> : <span className="text-sm text-positive">{t.product.dataFresh}</span>)}
            <span className="text-sm text-secondary">
              {t.scan.resultCountLabel}{" "}
              <span className="finance-value text-foreground">{results.length || "—"}</span>
            </span>
          </div>
        </header>
      )}

      {embedded && (
        <ScanScoringNote
          scoringEngineUsed={scoringEngineUsed}
          paritySummary={paritySummary}
          lastScanAt={lastScanAt}
          scanStale={scanStale}
        />
      )}

      <ScanCommandBar
        options={options}
        onChange={setOptions}
        onScan={handleScan}
        onReset={resetFilters}
        scanning={scanning}
        advancedFilterCount={advancedCount}
        savedScansSlot={
          <SavedScansMenu scans={savedScans} onLoad={handleLoadSavedScan} onDelete={handleDeleteSavedScan} />
        }
        saveSlot={
          <button
            type="button"
            onClick={() => void handleSaveCurrentScan()}
            disabled={savingScan || results.length === 0}
            className="scan-command-bar__btn"
          >
            {savingScan ? t.common.saving : t.scan.saveSnapshot}
          </button>
        }
        overflowSlot={
          <button type="button" onClick={() => void loadLatestScan()} className="scan-command-bar__btn">
            {t.scan.loadLastScan}
          </button>
        }
      />

      <ScanInlineStatus
        status={status}
        scanning={scanning}
        progress={progress}
        message={message}
        lastScanAt={lastScanAt}
        strategyVersion={strategyVersion}
        scoringEngineUsed={scoringEngineUsed}
        paritySummary={paritySummary}
        scanStale={scanStale}
        resultCount={results.length}
      />

      {(scanning || status === "running") && <ScanProgressBar progress={progress} message={message} />}

      {saveMsg && (
        <p className={clsx("text-sm", saveMsgSuccess ? "text-positive" : "text-amber-300")} role="status">
          {saveMsg}
        </p>
      )}

      <StockTable
        results={results}
        onAddWatchlist={handleWatchlist}
        watchlistAdded={watchlistAdded}
        watchlistPending={watchlistPending}
        heldPositions={heldPositions}
        scoringEngineUsed={scoringEngineUsed}
        scanAt={lastScanAt}
      />
    </div>
  );
}
