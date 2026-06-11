import clsx from "clsx";
import type { CockpitStatus } from "@/lib/dailyDecisionUtils";
import { useTranslation } from "@/lib/i18n";

const STYLES: Record<CockpitStatus, string> = {
  ready: "border-brand/35 bg-brand/10 text-brand",
  fresh: "border-brand/35 bg-brand/10 text-brand",
  needs_review: "border-amber-500/35 bg-amber-500/10 text-amber-200",
  demo: "border-amber-500/35 bg-amber-500/10 text-amber-200",
  import_needed: "border-sky-500/35 bg-sky-500/10 text-sky-200",
  missing: "border-sky-500/35 bg-sky-500/10 text-sky-200",
  stale: "border-zinc-600/50 bg-zinc-800/60 text-zinc-300",
  updating: "border-sky-400/35 bg-sky-500/10 text-sky-200",
};

export function CockpitStatusPill({ status }: { status: CockpitStatus }) {
  const { t } = useTranslation();
  const labels: Record<CockpitStatus, string> = {
    ready: t.home.dailyStatusReady,
    fresh: t.home.dailyStatusFresh,
    needs_review: t.home.dailyStatusNeedsReview,
    demo: t.home.dailyStatusDemo,
    import_needed: t.home.dailyStatusImportNeeded,
    missing: t.home.dailyStatusMissing,
    stale: t.home.dailyStatusStale,
    updating: t.home.dailyStatusUpdating,
  };
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold",
        STYLES[status]
      )}
      role="status"
    >
      <span
        className={clsx("h-1.5 w-1.5 rounded-full bg-current opacity-90", status === "updating" && "animate-pulse")}
        aria-hidden
      />
      {labels[status]}
    </span>
  );
}
