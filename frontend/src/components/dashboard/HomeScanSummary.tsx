"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { ScanScoreMeta } from "@/components/ScanScoreMeta";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { getLatestScan } from "@/lib/api";
import { getBucketMeta } from "@/lib/buckets";
import { formatDateTime } from "@/lib/datetime";
import { isStaleTimestamp } from "@/lib/quantHealth";
import type { Bucket, LatestScanResponse } from "@/lib/types";
import { fmt, useTranslation, useTRef } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const BUCKETS: Bucket[] = ["penny", "medium", "compounder"];
const STALE_MS = 24 * 60 * 60 * 1000;

export function HomeScanSummary() {
  const { t } = useTranslation();
  const tRef = useTRef();
  const bucketMeta = getBucketMeta(t);
  const [scans, setScans] = useState<Partial<Record<Bucket, LatestScanResponse>>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled(BUCKETS.map((b) => getLatestScan(b)));
      const next: Partial<Record<Bucket, LatestScanResponse>> = {};
      BUCKETS.forEach((b, i) => {
        const r = results[i];
        if (r.status === "fulfilled") next[b] = r.value;
      });
      setScans(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : tRef.current.home.scanSummaryFailed);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <section className="surface-card p-4">
      <SectionHeader
        title={t.home.scanSummaryTitle}
        subtitle={t.home.scanSummarySubtitle}
        action={
          <Link href="/scan" className="text-xs text-[#7dff8e] hover:underline">
            {t.home.openScan}
          </Link>
        }
      />
      {loading && <LoadingSkeleton lines={3} />}
      {!loading && error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {BUCKETS.map((bucket) => {
            const data = scans[bucket];
            const count = data?.results?.length ?? 0;
            const stale = isStaleTimestamp(data?.completed_at, STALE_MS);
            return (
              <div key={bucket} className="rounded-lg border border-zinc-800 bg-zinc-950/40 p-3">
                <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                  {bucketMeta[bucket].label}
                </p>
                <p className="mt-1 text-2xl font-semibold tabular-nums text-[#7dff8e]">{count}</p>
                <p className="mt-1 text-xs text-zinc-500">
                  {data?.completed_at
                    ? fmt(t.home.scanAsOf, { time: formatDateTime(data.completed_at) })
                    : t.home.noScanYet}
                </p>
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  {stale && data?.completed_at && <StaleDataBadge asOf={data.completed_at} />}
                  {data?.scoring_engine_used != null && (
                    <ScoreSourceBadge
                      source={data.scoring_engine_used ? "scoring_engine_v2" : "legacy_screener"}
                    />
                  )}
                </div>
                {data?.parity_summary && (
                  <div className="mt-2">
                    <ScanScoreMeta
                      scoringEngineUsed={data.scoring_engine_used}
                      paritySummary={data.parity_summary}
                    />
                  </div>
                )}
                <Link
                  href={`/scan?bucket=${bucket}`}
                  className="mt-2 inline-block text-xs text-zinc-400 hover:text-[#7dff8e]"
                >
                  {t.home.viewBucket}
                </Link>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
