import type { Bucket } from "@/lib/types";
import type { Messages } from "@/lib/i18n/messages/en";

export const BUCKET_ORDER: Bucket[] = ["penny", "medium", "compounder"];

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

export function parseBucket(value: string | null | undefined): Bucket {
  if (value === "penny" || value === "medium" || value === "compounder") return value;
  return "medium";
}
