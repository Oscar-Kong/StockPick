// Unified scan page with penny / compounder bucket tabs.
"use client";

import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { BucketPage, type ScanPageMeta } from "@/components/BucketPage";
import { PageContainer } from "@/components/ui/PageContainer";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ACTIVE_BUCKET_ORDER, getBucketMeta, parseBucket } from "@/lib/buckets";
import { formatDateTime } from "@/lib/datetime";
import { useTranslation } from "@/lib/i18n";
import type { Bucket } from "@/lib/types";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";
import { StaleDataBadge } from "./badges/StaleDataBadge";

function ScanHubContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const bucket = parseBucket(searchParams.get("bucket"));
  const bucketMeta = getBucketMeta(t);
  const [meta, setMeta] = useState<ScanPageMeta | null>(null);

  const setBucket = useCallback(
    (next: Bucket) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("bucket", next);
      router.replace(`/scan?${params.toString()}`);
    },
    [router, searchParams]
  );

  const activeMeta = meta ?? {
    bucket,
    bucketLabel: bucketMeta[bucket].label,
    description: bucketMeta[bucket].description,
    lastScanAt: null,
    scanStale: false,
    resultCount: 0,
  };

  return (
    <PageContainer full className="scan-hub flex min-h-0 flex-1 flex-col gap-2">
      <header className="scan-page-header scan-page-header--hub">
        <div className="scan-page-header__primary">
          <div className="scan-page-header__title-row">
            <h1 className="scan-page-header__title">{t.scan.hubTitle}</h1>
            <span className="chip px-2 py-0.5 text-sm">{activeMeta.bucketLabel}</span>
          </div>
          <p className="scan-page-header__desc">{activeMeta.description}</p>
        </div>
        <div className="scan-page-header__status-cluster" aria-label={t.scan.statusClusterAria}>
          {activeMeta.lastScanAt && (
            <span className="scan-page-header__status-item text-sm text-secondary">
              {t.scan.lastScanLabel}{" "}
              <span className="finance-value">{formatDateTime(activeMeta.lastScanAt)}</span>
            </span>
          )}
          {activeMeta.lastScanAt &&
            (activeMeta.scanStale ? (
              <StaleDataBadge asOf={activeMeta.lastScanAt} />
            ) : (
              <span className="text-sm text-positive">{t.product.dataFresh}</span>
            ))}
          <span className="scan-page-header__status-item text-sm text-secondary">
            {t.scan.resultCountLabel}{" "}
            <span className="finance-value text-foreground">{activeMeta.resultCount || "—"}</span>
          </span>
          <Link
            href="/library?tab=scans"
            className="scan-page-header__library-link text-sm font-medium text-primary hover:underline"
          >
            {t.nav.library}
          </Link>
        </div>
        <AppTabBar aria-label={t.scan.bucketsAria} className="scan-page-header__buckets">
          {ACTIVE_BUCKET_ORDER.map((b) => (
            <AppTabButton key={b} active={bucket === b} onClick={() => setBucket(b)}>
              {bucketMeta[b].label}
            </AppTabButton>
          ))}
        </AppTabBar>
      </header>

      <div className="scan-hub__workspace flex min-h-0 flex-1 flex-col">
        <BucketPage key={bucket} bucket={bucket} embedded onMetaChange={setMeta} />
      </div>
    </PageContainer>
  );
}

function ScanHubLoading() {
  return <LoadingSkeleton lines={6} className="max-w-3xl" />;
}

export function ScanHub() {
  return (
    <Suspense fallback={<ScanHubLoading />}>
      <ScanHubContent />
    </Suspense>
  );
}
