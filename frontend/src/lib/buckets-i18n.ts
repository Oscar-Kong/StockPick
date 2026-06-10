import type { Bucket } from "@/lib/types";
import type { Messages } from "@/lib/i18n/messages/en";

/** User-facing scan tabs (active product buckets). */
export const ACTIVE_BUCKET_ORDER: Bucket[] = ["penny", "compounder"];

/** Legacy bucket — readable in saved data, not offered for new scans. */
export const DEPRECATED_BUCKETS: Bucket[] = ["medium"];

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
    medium: {
      label: t.buckets.medium.label,
      title: t.buckets.medium.title,
      description: t.buckets.medium.description,
    },
    compounder: {
      label: t.buckets.compounder.label,
      title: t.buckets.compounder.title,
      description: t.buckets.compounder.description,
    },
  };
}

/** Parse URL/query bucket; defaults to penny. Deprecated medium maps to penny for scans. */
export function parseBucket(value: string | null | undefined): Bucket {
  if (value === "penny" || value === "compounder") return value;
  if (value === "medium") return "penny";
  return DEFAULT_BUCKET;
}

/** Bucket fit display: active buckets + legacy medium if present in data. */
export function bucketFitDisplayOrder(scores: Partial<Record<Bucket, unknown>>): Bucket[] {
  const order: Bucket[] = [...ACTIVE_BUCKET_ORDER];
  if (scores.medium != null && !order.includes("medium")) {
    order.splice(1, 0, "medium");
  }
  return order;
}
