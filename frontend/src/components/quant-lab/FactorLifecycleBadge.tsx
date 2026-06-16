"use client";

import type { FactorLifecycleStatus } from "@/lib/researchReliability";
import { useTranslation } from "@/lib/i18n";

const LIFECYCLE_STYLES: Record<FactorLifecycleStatus, string> = {
  promote: "border-emerald-900/50 bg-emerald-950/40 text-emerald-200",
  keep: "border-zinc-700 bg-zinc-900/60 text-zinc-300",
  watch: "border-amber-900/50 bg-amber-950/40 text-amber-200",
  retire: "border-rose-900/50 bg-rose-950/40 text-rose-200",
  insufficient_evidence: "border-zinc-800 bg-zinc-950/40 text-zinc-500",
};

export function FactorLifecycleBadge({ status }: { status: FactorLifecycleStatus }) {
  const { t } = useTranslation();
  const labels: Record<FactorLifecycleStatus, string> = {
    promote: t.reliability.lifecyclePromote,
    keep: t.reliability.lifecycleKeep,
    watch: t.reliability.lifecycleWatch,
    retire: t.reliability.lifecycleRetire,
    insufficient_evidence: t.reliability.lifecycleInsufficient,
  };
  return (
    <span
      className={`inline-flex shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${LIFECYCLE_STYLES[status]}`}
      data-testid={`factor-lifecycle-${status}`}
    >
      {labels[status]}
    </span>
  );
}
