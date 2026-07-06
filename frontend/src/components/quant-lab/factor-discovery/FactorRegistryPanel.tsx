"use client";

import { getFactorRegistryDetail, listFactorRegistry } from "@/lib/api/factorDiscovery/client";
import { parseFactorDiscoveryError } from "@/lib/api/factorDiscovery/errors";
import type { FactorRegistryItem } from "@/lib/api/factorDiscovery/types";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { useCallback, useEffect, useState } from "react";

export function FactorRegistryPanel() {
  const [items, setItems] = useState<FactorRegistryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listFactorRegistry({ search: search || undefined, limit: 100 }, signal);
      setItems(res.items);
    } catch (e) {
      if (signal?.aborted) return;
      setError(parseFactorDiscoveryError(e).message);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    const controller = new AbortController();
    setDetailLoading(true);
    getFactorRegistryDetail(selectedId, controller.signal)
      .then((res) => setDetail(res as Record<string, unknown>))
      .catch(() => setDetail(null))
      .finally(() => {
        if (!controller.signal.aborted) setDetailLoading(false);
      });
    return () => controller.abort();
  }, [selectedId]);

  if (loading && items.length === 0) return <LoadingSkeleton lines={5} />;
  if (error && items.length === 0) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          className="rounded border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-600 dark:bg-zinc-950"
          placeholder="Search factors"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search factor registry"
        />
        <button type="button" className="rounded border px-2 py-1 text-sm" onClick={() => load()}>
          Search
        </button>
      </div>

      {items.length === 0 ? (
        <EmptyState title="No factor definitions" message="Approved formulas appear here after review." />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-xs">
              <thead>
                <tr className="border-b border-zinc-200 text-zinc-500 dark:border-zinc-700">
                  <th className="py-1 text-left">Factor</th>
                  <th className="py-1 text-left">Version</th>
                  <th className="py-1 text-left">Lifecycle</th>
                  <th className="py-1 text-left">Direction</th>
                  <th className="py-1 text-left">Research gate</th>
                  <th className="py-1 text-left">Promising</th>
                </tr>
              </thead>
              <tbody>
                {items.map((f) => (
                  <tr
                    key={f.factor_id}
                    className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                    onClick={() => setSelectedId(f.factor_id)}
                  >
                    <td className="py-1.5">{f.display_name || f.factor_id}</td>
                    <td className="py-1.5">{f.latest_version}</td>
                    <td className="py-1.5">{f.lifecycle_status}</td>
                    <td className="py-1.5">{f.expected_direction}</td>
                    <td className="py-1.5">{f.latest_acceptance_status ?? "—"}</td>
                    <td className="py-1.5">{f.latest_promising_status ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <aside className="rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
            {!selectedId ? (
              <p className="text-sm text-zinc-500">Select a factor for detail.</p>
            ) : detailLoading ? (
              <LoadingSkeleton lines={4} />
            ) : detail ? (
              <div className="space-y-2 text-xs">
                <h3 className="text-sm font-semibold">{String(detail.display_name ?? selectedId)}</h3>
                <p>
                  Lifecycle: <strong>{String(detail.lifecycle_status ?? "—")}</strong>
                </p>
                <p>
                  Latest research gate: <strong>{String(detail.latest_acceptance_status ?? "—")}</strong>
                </p>
                <p>
                  Promising review: <strong>{detail.latest_promising_status ? "YES" : "NO"}</strong>
                </p>
                <pre className="max-h-40 overflow-auto rounded bg-zinc-950 p-2 font-mono text-[10px] text-zinc-100">
                  {String((detail as { canonical_dsl?: string }).canonical_dsl ?? detail.canonical_dsl_summary ?? "—")}
                </pre>
                <p className="text-zinc-500">Versions: {String(detail.version_count ?? "—")}</p>
              </div>
            ) : (
              <p className="text-sm text-red-600">Failed to load factor detail.</p>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}
