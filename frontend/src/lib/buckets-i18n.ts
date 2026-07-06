import type { Bucket } from "@/lib/types";
import type { Messages } from "@/lib/i18n/messages/en";

/** User-facing scan tabs (active product buckets). */
export const ACTIVE_BUCKET_ORDER: Bucket[] = ["penny", "compounder"];

/** @deprecated Use ACTIVE_BUCKET_ORDER for scan UI. */
export const BUCKET_ORDER: Bucket[] = ACTIVE_BUCKET_ORDER;

export const DEFAULT_BUCKET: Bucket = "penny";

export function isActiveBucket(bucket: Bucket): boolean {
  return bucket === "penny" || bucket === "compounder";
}

export function getBucketMeta(t: Messages): Record<
  Bucket,
  { label: string; title: string; description: string }
> {
  return {
    penny: {
      label: t.buckets.penny.label,
      title: t.buckets.penny.title,
      description: t.buckets.penny.description,
    },
    compounder: {
      label: t.buckets.compounder.label,
      title: t.buckets.compounder.title,
      description: t.buckets.compounder.description,
    },
  };
}

/** Parse URL/query bucket; defaults to penny. Legacy `medium` maps to penny. */
export function parseBucket(value: string | null | undefined): Bucket {
  if (value === "penny" || value === "compounder") return value;
  if (value === "medium") return "penny";
  return DEFAULT_BUCKET;
}

/** Normalize watchlist/API bucket strings for active sleeves only. */
export function normalizeBucket(value: string | null | undefined): Bucket {
  return parseBucket(value);
}

/** Bucket fit display order for analysis sidebar. */
export function bucketFitDisplayOrder(_scores: Partial<Record<Bucket, unknown>>): Bucket[] {
  return [...ACTIVE_BUCKET_ORDER];
}
