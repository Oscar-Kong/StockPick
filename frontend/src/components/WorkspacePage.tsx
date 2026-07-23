// Watchlist + live analysis in one workspace.
"use client";

import { AnalysisPanel } from "@/components/AnalysisPanel";
import { WatchlistImport } from "@/components/WatchlistImport";
import { WatchlistRail } from "@/components/WatchlistRail";
import { ErrorState } from "@/components/ui/ErrorState";
import { WorkspaceEmptyPanel } from "@/components/WorkspaceEmptyPanel";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import {
  getAnalyzeWatchlist,
  getWatchlist,
  refreshWatchlist,
  removeFromWatchlist,
} from "@/lib/api";
import { normalizeBucket } from "@/lib/buckets";
import { fmt, useTranslation } from "@/lib/i18n";
import type { AnalyzeWatchlistRow, WatchlistItem } from "@/lib/types";
import { explainWorkspaceLoadError } from "@/lib/workspaceLoadError";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

function WorkspaceContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const initialSymbol = searchParams.get("symbol")?.toUpperCase() ?? null;
  const tabParam = searchParams.get("tab");

  useEffect(() => {
    if (tabParam === "journal") {
      router.replace("/?tab=activity");
      return;
    }
    if (tabParam === "compare") {
      const params = new URLSearchParams(searchParams.toString());
      params.delete("tab");
      const qs = params.toString();
      router.replace(qs ? `/workspace?${qs}` : "/workspace");
    }
  }, [tabParam, router, searchParams]);

  const [matrix, setMatrix] = useState<AnalyzeWatchlistRow[]>([]);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [alertTotal, setAlertTotal] = useState(0);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(initialSymbol);
  const [selectedNotes, setSelectedNotes] = useState("");
  const [selectedBucket, setSelectedBucket] = useState<AnalyzeWatchlistRow["bucket"] | undefined>();
  const [railLoading, setRailLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("");
  const [showImport, setShowImport] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const autoPickedRef = useRef(false);
  const selectedRef = useRef(selectedSymbol);

  useEffect(() => {
    selectedRef.current = selectedSymbol;
  }, [selectedSymbol]);

  const symbolOrder = useMemo(() => items.map((i) => i.symbol.toUpperCase()), [items]);
  const selectedIndex = selectedSymbol ? symbolOrder.indexOf(selectedSymbol.toUpperCase()) : -1;
  const prevSymbol = selectedIndex > 0 ? symbolOrder[selectedIndex - 1] : null;
  const nextSymbol =
    selectedIndex >= 0 && selectedIndex < symbolOrder.length - 1
      ? symbolOrder[selectedIndex + 1]
      : null;

  const matrixBySymbol = useMemo(
    () => new Map(matrix.map((r) => [r.symbol, r])),
    [matrix]
  );

  const selectSymbol = useCallback(
    (sym: string) => {
      const upper = sym.toUpperCase();
      setSelectedSymbol(upper);
      const row = matrixBySymbol.get(upper);
      setSelectedNotes(row?.notes ?? "");
      setSelectedBucket(normalizeBucket(row?.bucket));
      const params = new URLSearchParams(window.location.search);
      params.set("symbol", upper);
      params.delete("tab");
      window.history.replaceState(null, "", `/workspace?${params.toString()}`);
    },
    [matrixBySymbol]
  );

  const loadRail = useCallback(async () => {
    setRailLoading(true);
    setFetchError(null);
    try {
      const [analyzeRes, watchlist] = await Promise.all([
        getAnalyzeWatchlist(),
        getWatchlist(),
      ]);
      setMatrix(analyzeRes.rows);
      setAlertTotal(analyzeRes.alert_total);
      setItems(watchlist);

      const current = selectedRef.current;
      if (current) {
        const row = analyzeRes.rows.find((r) => r.symbol === current);
        if (row) {
          setSelectedNotes(row.notes);
          setSelectedBucket(normalizeBucket(row.bucket));
        }
      } else if (
        !autoPickedRef.current &&
        !initialSymbol &&
        analyzeRes.rows.length > 0
      ) {
        autoPickedRef.current = true;
        const first = analyzeRes.rows[0];
        setSelectedSymbol(first.symbol);
        setSelectedNotes(first.notes);
        setSelectedBucket(normalizeBucket(first.bucket));
      }
    } catch (err) {
      setMatrix([]);
      setItems([]);
      setFetchError(explainWorkspaceLoadError(err, t));
    } finally {
      setRailLoading(false);
    }
  }, [initialSymbol, t]);

  useEffect(() => {
    void loadRail();
  }, [loadRail]);

  useEffect(() => {
    if (initialSymbol) {
      setSelectedSymbol(initialSymbol);
      const row = matrixBySymbol.get(initialSymbol);
      if (row) {
        setSelectedNotes(row.notes);
        setSelectedBucket(normalizeBucket(row.bucket));
      }
    }
  }, [initialSymbol, matrixBySymbol]);

  const handleRefresh = async () => {
    setRefreshing(true);
    setMsg(null);
    try {
      const res = await refreshWatchlist();
      setMsg(fmt(t.workspace.refreshed, { count: res.refreshed }));
      await loadRail();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : t.workspace.refreshFailed);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRemove = async (symbol: string) => {
    await removeFromWatchlist(symbol);
    if (selectedSymbol === symbol) {
      setSelectedSymbol(null);
      router.replace("/workspace");
    }
    await loadRail();
  };

  const metaAlerts =
    alertTotal > 0
      ? fmt(t.workspace.alertSuffix, {
          count: alertTotal,
          label: alertTotal === 1 ? t.common.alert : t.common.alerts,
        })
      : "";
  const metaSelected = selectedSymbol
    ? fmt(t.workspace.selectedSuffix, { symbol: selectedSymbol })
    : "";

  return (
    <div className="workspace-layout workspace-layout--fill">
      <header className="workspace-toolbar shrink-0">
        <div className="workspace-toolbar-title">
          <h1>{t.workspace.title}</h1>
          <span className="workspace-toolbar-meta">
            {fmt(t.workspace.meta, {
              count: items.length,
              alerts: metaAlerts,
              selected: metaSelected,
            })}
          </span>
        </div>
      </header>

      {fetchError && (
        <div className="workspace-fetch-notice shrink-0 px-3 pb-2 md:px-4">
          <ErrorState
            message={`${t.workspace.fetchFailedTitle}. ${fetchError}`}
            onRetry={() => void loadRail()}
          />
        </div>
      )}

      <div className="workspace-research">
        <div className="workspace-frame">
          <aside className="workspace-rail hidden md:flex">
            <WatchlistRail
              items={items}
              matrixBySymbol={matrixBySymbol}
              selected={selectedSymbol}
              filter={filter}
              onFilterChange={setFilter}
              onSelect={selectSymbol}
              onRemove={(s) => void handleRemove(s)}
              onRefresh={() => void handleRefresh()}
              onToggleImport={() => setShowImport((v) => !v)}
              showImport={showImport}
              refreshing={refreshing}
              loading={railLoading}
              msg={msg}
              onImported={() => void loadRail()}
            />
          </aside>

          <div className="workspace-main">
            <div className="workspace-analyze-pane">
              {showImport && (
                <div className="shrink-0 border-b border-zinc-800 bg-zinc-950/80 p-4 md:hidden">
                  <WatchlistImport onImported={() => void loadRail()} />
                </div>
              )}

              <div className="shrink-0 border-b border-zinc-800 p-2 md:hidden">
                <select
                  value={selectedSymbol ?? ""}
                  onChange={(e) => e.target.value && selectSymbol(e.target.value)}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
                >
                  <option value="">{t.workspace.selectSymbol}</option>
                  {items.map((i) => (
                    <option key={i.symbol} value={i.symbol}>
                      {i.symbol} ({i.bucket})
                    </option>
                  ))}
                </select>
              </div>

              {selectedSymbol ? (
                <AnalysisPanel
                  symbol={selectedSymbol}
                  bucket={selectedBucket}
                  initialNotes={selectedNotes}
                  embedded
                  prevSymbol={prevSymbol}
                  nextSymbol={nextSymbol}
                  onNavigateSymbol={selectSymbol}
                />
              ) : (
                <WorkspaceEmptyPanel
                  items={items}
                  matrixBySymbol={matrixBySymbol}
                  onSelect={selectSymbol}
                  onToggleImport={() => setShowImport(true)}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function WorkspacePage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={5} className="p-4" />}>
      <WorkspaceContent />
    </Suspense>
  );
}
