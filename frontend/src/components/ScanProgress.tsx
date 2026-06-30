// Progress indicator for active screening jobs and status messages.
"use client";

import { useTranslation } from "@/lib/i18n";

interface ScanProgressProps {
  progress: number;
  message: string;
  status: string;
}

export function ScanProgress({ progress, message, status }: ScanProgressProps) {
  const { t } = useTranslation();

  const statusLabel: Record<string, string> = {
    idle: t.scan.statusIdle,
    running: t.scan.statusRunning,
    completed: t.scan.statusCompleted,
    failed: t.scan.statusFailed,
  };

  if (status === "completed" && progress >= 100) {
    return null;
  }

  return (
    <div className="surface-card p-4 sm:p-5">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
            {t.scan.progressLabel}
          </p>
          <p className="mt-1 text-sm font-semibold text-zinc-100">
            {statusLabel[status] ?? status}
          </p>
        </div>
        <p className="text-2xl font-semibold tabular-nums text-[#7dff8e]">{progress.toFixed(0)}%</p>
      </div>
      <div className="h-2.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className="h-full rounded-full bg-primary transition-all"
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>
      {message && (
        <p className="mt-3 text-xs leading-relaxed text-zinc-500">{message}</p>
      )}
    </div>
  );
}
