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
    <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="mb-2 flex items-center justify-between text-sm">
        <span className="font-medium">{statusLabel[status] ?? status}</span>
        <span className="text-zinc-500">{progress.toFixed(0)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        <div
          className="h-full rounded-full bg-zinc-900 transition-all dark:bg-zinc-100"
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>
      <p className="mt-2 text-xs text-zinc-500">{message}</p>
    </div>
  );
}
