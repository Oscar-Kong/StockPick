// Unified scan page with penny / compounder bucket tabs.
"use client";

import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { BucketPage } from "@/components/BucketPage";
import { PageHeader } from "@/components/ui/PageHeader";
import { ACTIVE_BUCKET_ORDER, getBucketMeta, parseBucket } from "@/lib/buckets";
import { useTranslation } from "@/lib/i18n";
import type { Bucket } from "@/lib/types";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback } from "react";

function ScanHubContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const router = useRouter();
  const bucket = parseBucket(searchParams.get("bucket"));
  const bucketMeta = getBucketMeta(t);

  const setBucket = useCallback(
    (next: Bucket) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("bucket", next);
      router.replace(`/scan?${params.toString()}`);
    },
    [router, searchParams]
  );

  const meta = bucketMeta[bucket];

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4">
      <PageHeader
        title={t.scan.hubTitle}
        subtitle={
          <>
            {t.scan.hubSubtitle}{" "}
            <Link href="/library?tab=scans" className="font-medium text-brand hover:underline">
              {t.nav.library}
            </Link>
          </>
        }
        actions={
          <AppTabBar aria-label={t.scan.bucketsAria}>
            {ACTIVE_BUCKET_ORDER.map((b) => (
              <AppTabButton key={b} active={bucket === b} onClick={() => setBucket(b)}>
                {bucketMeta[b].label}
              </AppTabButton>
            ))}
          </AppTabBar>
        }
      />
      <p className="text-sm text-zinc-500">{meta.description}</p>
      <div className="min-h-0 flex-1">
        <BucketPage key={bucket} bucket={bucket} title={meta.title} description={meta.description} embedded />
      </div>
    </div>
  );
}

function ScanHubLoading() {
  const { t } = useTranslation();
  return <p className="text-sm text-zinc-500">{t.scan.loading}</p>;
}

export function ScanHub() {
  return (
    <Suspense fallback={<ScanHubLoading />}>
      <ScanHubContent />
    </Suspense>
  );
}
