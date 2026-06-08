import type { Bucket } from "@/lib/types";

export { BUCKET_ORDER, getBucketMeta, parseBucket } from "./buckets-i18n";

/** @deprecated Use getBucketMeta(t) from buckets-i18n with useTranslation */
export const BUCKET_META: Record<
  Bucket,
  { label: string; title: string; description: string }
> = {
  penny: {
    label: "Penny",
    title: "Penny Stocks",
    description:
      "Short-term momentum plays (days to ~2 weeks). High risk — use small position sizes.",
  },
  medium: {
    label: "Medium",
    title: "Medium-Term",
    description:
      "Swing setups (weeks to a few months). Balance momentum with fundamentals and risk controls.",
  },
  compounder: {
    label: "Compounder",
    title: "Long-Term Compounders",
    description:
      "Quality growers held for years. Macro and governance matter more than short-term noise.",
  },
};
