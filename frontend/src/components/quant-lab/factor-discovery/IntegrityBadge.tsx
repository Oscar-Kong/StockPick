"use client";

import type { IntegrityStatus } from "@/lib/api/factorDiscovery/types";

const LABELS: Record<IntegrityStatus, string> = {
  VERIFIED: "Verified",
  NOT_VERIFIED: "Not verified",
  FAILED: "Integrity failed",
  UNAVAILABLE: "Unavailable",
};

const STYLES: Record<IntegrityStatus, string> = {
  VERIFIED: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  NOT_VERIFIED: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
  FAILED: "bg-red-500/15 text-red-700 dark:text-red-300",
  UNAVAILABLE: "bg-zinc-500/15 text-zinc-700 dark:text-zinc-300",
};

export function IntegrityBadge({
  status,
  errorSummary,
  className = "",
}: {
  status: IntegrityStatus;
  errorSummary?: string | null;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${STYLES[status]} ${className}`}
      role="status"
      aria-label={`Integrity: ${LABELS[status]}${errorSummary ? `. ${errorSummary}` : ""}`}
    >
      {LABELS[status]}
    </span>
  );
}
