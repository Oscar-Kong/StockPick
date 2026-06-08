"use client";

import { useTranslation } from "@/lib/i18n";
import type { V2UnavailableReason } from "@/lib/v2Score";
import clsx from "clsx";

interface V2FallbackBannerProps {
  reason: V2UnavailableReason;
  className?: string;
}

export function V2FallbackBanner({ reason, className }: V2FallbackBannerProps) {
  const { t } = useTranslation();
  const message =
    reason === "disabled"
      ? t.analysis.v2DisabledFallback
      : reason === "not_found"
        ? t.analysis.v2NotFoundFallback
        : t.analysis.v2ErrorFallback;

  return (
    <div
      className={clsx(
        "rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-100/90",
        className
      )}
      role="status"
    >
      {message}
    </div>
  );
}
