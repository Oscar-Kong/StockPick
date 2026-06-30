"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";
import { LoadingSkeleton } from "./LoadingSkeleton";

export type AsyncState =
  | "idle"
  | "loading"
  | "refreshing"
  | "success"
  | "empty"
  | "error"
  | "stale"
  | "partial";

interface AsyncStateShellProps {
  state: AsyncState;
  children?: React.ReactNode;
  className?: string;
  /** Keep children visible during refresh or partial loads. */
  preserveContent?: boolean;
  loadingText?: string;
  emptyTitle?: string;
  emptyMessage?: string;
  errorMessage?: string | null;
  staleMessage?: string;
  partialMessage?: string;
  onRetry?: () => void;
  emptyAction?: React.ReactNode;
  skeletonLines?: number;
  role?: string;
  "aria-live"?: "off" | "polite" | "assertive";
}

function AsyncBanner({
  tone,
  children,
}: {
  tone: "info" | "warn" | "error";
  children: React.ReactNode;
}) {
  const toneClass =
    tone === "error"
      ? "async-state-banner--error"
      : tone === "warn"
        ? "async-state-banner--warn"
        : "async-state-banner--info";
  return (
    <p className={clsx("async-state-banner", toneClass)} role="status">
      {children}
    </p>
  );
}

/** Unified async-state presentation for data panels, tables, and charts. */
export function AsyncStateShell({
  state,
  children,
  className,
  preserveContent = false,
  loadingText,
  emptyTitle,
  emptyMessage,
  errorMessage,
  staleMessage,
  partialMessage,
  onRetry,
  emptyAction,
  skeletonLines = 3,
  role,
  "aria-live": ariaLive = "polite",
}: AsyncStateShellProps) {
  const { t } = useTranslation();
  const resolvedLoading = loadingText ?? t.common.loading;
  const resolvedEmpty = emptyMessage ?? "No data.";

  if (state === "idle") {
    return null;
  }

  if (state === "loading") {
    return (
      <div className={className} role={role} aria-live={ariaLive} aria-busy="true">
        <LoadingSkeleton lines={skeletonLines} />
        <span className="sr-only">{resolvedLoading}</span>
      </div>
    );
  }

  if (state === "error" && errorMessage) {
    return (
      <div className={className} role={role} aria-live={ariaLive}>
        <ErrorState message={errorMessage} onRetry={onRetry} />
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className={className} role={role} aria-live={ariaLive}>
        <EmptyState title={emptyTitle} message={resolvedEmpty} action={emptyAction} />
      </div>
    );
  }

  const showChildren =
    state === "success" ||
    state === "stale" ||
    state === "partial" ||
    (state === "refreshing" && preserveContent);

  if (!showChildren) {
    return null;
  }

  return (
    <div className={className} role={role} aria-live={ariaLive}>
      {state === "refreshing" && (
        <AsyncBanner tone="info">{resolvedLoading}</AsyncBanner>
      )}
      {state === "stale" && staleMessage && (
        <AsyncBanner tone="warn">{staleMessage}</AsyncBanner>
      )}
      {state === "partial" && partialMessage && (
        <AsyncBanner tone="warn">{partialMessage}</AsyncBanner>
      )}
      {children}
    </div>
  );
}

/** Map legacy AsyncSection states to AsyncStateShell. */
export function legacyAsyncState(
  state: "idle" | "loading" | "error" | "empty" | "ready",
  options?: { refreshing?: boolean }
): AsyncState {
  if (state === "ready") return "success";
  if (state === "loading" && options?.refreshing) return "refreshing";
  return state;
}
