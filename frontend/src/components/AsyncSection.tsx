"use client";

import { AsyncStateShell, legacyAsyncState } from "@/components/ui/AsyncStateShell";

type AsyncSectionState = "idle" | "loading" | "error" | "empty" | "ready";

interface AsyncSectionProps {
  state: AsyncSectionState;
  loadingText?: string;
  errorText?: string | null;
  emptyText?: string;
  onRetry?: () => void;
  children: React.ReactNode;
  className?: string;
  /** When true, keep showing children during loading (e.g. refresh) with a subtle banner. */
  preserveOnRefresh?: boolean;
  refreshing?: boolean;
}

/** Compatibility wrapper — prefer AsyncStateShell for new code. */
export function AsyncSection({
  state,
  loadingText,
  errorText,
  emptyText,
  onRetry,
  children,
  className,
  preserveOnRefresh = false,
  refreshing = false,
}: AsyncSectionProps) {
  if (state === "loading" && !preserveOnRefresh) {
    return (
      <p className={`text-xs text-zinc-500${className ? ` ${className}` : ""}`} role="status">
        {loadingText ?? "Loading…"}
      </p>
    );
  }

  const shellState = legacyAsyncState(state, { refreshing: preserveOnRefresh && refreshing });

  return (
    <AsyncStateShell
      state={shellState}
      className={className}
      preserveContent={preserveOnRefresh}
      loadingText={loadingText}
      emptyMessage={emptyText}
      errorMessage={errorText}
      onRetry={onRetry}
    >
      {children}
    </AsyncStateShell>
  );
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}
