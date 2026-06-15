"use client";

import { ScoreSourceBadge } from "@/components/ScoreSourceBadge";
import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatTile } from "@/components/ui/StatTile";
import { getLatestScan } from "@/lib/api";
import { ACTIVE_BUCKET_ORDER, getBucketMeta } from "@/lib/buckets";
import { formatDateTime } from "@/lib/datetime";
import { isStaleTimestamp } from "@/lib/quantHealth";
import type { Bucket, LatestScanResponse } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const BUCKETS: Bucket[] = ACTIVE_BUCKET_ORDER;
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
    <section className="surface-card p-4 sm:p-5">
      <SectionHeader
        title={t.home.scanSummaryTitle}
        subtitle={t.home.scanSummarySubtitle}
        action={
          <Link href="/scan?bucket=penny" className="text-xs text-[#7dff8e] hover:underline">
            {t.home.openScan}
          </Link>
        }
      />
      {loading && <LoadingSkeleton lines={3} />}
      {!loading && error && <ErrorState message={error} onRetry={() => void load()} />}
      {!loading && !error && (
        <div className="grid gap-4 lg:grid-cols-3">
          {BUCKETS.map((bucket) => {
            const data = scans[bucket];
            const count = data?.results?.length ?? 0;
            const stale = isStaleTimestamp(data?.completed_at, STALE_MS);
            const source =
              data?.scoring_engine_used == null
                ? null
                : data.scoring_engine_used
                  ? "scoring_engine_v2"
                  : "legacy_screener";

            return (
              <article
                key={bucket}
                className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-950/40 p-4"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-zinc-200">{bucketMeta[bucket].label}</h3>
                    <p className="mt-0.5 text-xs text-zinc-500">{bucketMeta[bucket].description}</p>
                  </div>
                  <Link
                    href={`/scan?bucket=${bucket}`}
                    className="shrink-0 text-xs text-zinc-400 hover:text-[#7dff8e]"
                  >
                    {t.home.viewBucket}
                  </Link>
                </div>

                <dl className="mt-4 grid gap-3 sm:grid-cols-2">
                  <StatTile
                    label={t.scan.resultCountLabel}
                    value={
                      <span className="tabular-nums text-xl text-[#7dff8e]">
                        {count > 0 ? count : "—"}
                      </span>
                    }
                    hint={count > 0 ? t.scan.candidatesRanked : t.home.noScanYet}
                  />
                  <StatTile
                    label={t.scan.lastScanLabel}
                    value={
                      data?.completed_at ? (
                        <span className="tabular-nums text-zinc-200">
                          {formatDateTime(data.completed_at)}
                        </span>
                      ) : (
                        "—"
                      )
                    }
                  />
                </dl>

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  {stale && data?.completed_at && <StaleDataBadge asOf={data.completed_at} />}
                  {source && <ScoreSourceBadge source={source} />}
                  {!stale && data?.completed_at && (
                    <span className="text-[11px] text-emerald-300/80">{t.product.dataFresh}</span>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
