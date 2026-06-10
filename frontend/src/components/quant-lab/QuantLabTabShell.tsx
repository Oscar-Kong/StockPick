"use client";

import { StaleDataBadge } from "@/components/badges/StaleDataBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { RetryButton } from "@/components/ui/RetryButton";
import { ACTIVE_BUCKET_ORDER } from "@/lib/buckets";
import type { ReactNode } from "react";

export function FeatureDisabledNotice({ message }: { message: string }) {
  return (
    <p className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs text-zinc-400">
      {message}
    </p>
  );
}

export function QuantLabEmptyState({ message }: { message: string }) {
  return <EmptyState message={message} />;
}

export function BucketSelect({
  value,
  onChange,
  label,
  includeDeprecated = false,
}: {
  value: string;
  onChange: (value: string) => void;
  label: string;
  /** Show legacy medium for historical data only */
  includeDeprecated?: boolean;
}) {
  return (
    <label className="text-xs text-zinc-500">
      {label}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="ml-2 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-sm"
      >
        {ACTIVE_BUCKET_ORDER.map((b) => (
          <option key={b} value={b}>
            {b}
          </option>
        ))}
        {includeDeprecated && value === "medium" && (
          <option value="medium">medium (legacy)</option>
        )}
      </select>
    </label>
  );
}

interface QuantLabTabLayoutProps {
  title: string;
  description?: ReactNode;
  statusBadge?: ReactNode;
  reliability?: ReactNode;
  controls?: ReactNode;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  disabled?: boolean;
  disabledMessage?: string;
  partialWarning?: string | null;
  children?: ReactNode;
}

/** Shared tab shell: header, controls, loading/error/disabled, then body. */
export function QuantLabTabLayout({
  title,
  description,
  statusBadge,
  reliability,
  controls,
  loading,
  error,
  onRetry,
  disabled,
  disabledMessage,
  partialWarning,
  children,
}: QuantLabTabLayoutProps) {
  return (
    <div className="space-y-4">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
          {statusBadge}
        </div>
        {description && <div className="text-xs text-zinc-500">{description}</div>}
      </header>
      {reliability}
      {controls}
      {loading && <LoadingSkeleton lines={4} />}
      {disabled && disabledMessage && <FeatureDisabledNotice message={disabledMessage} />}
      {partialWarning && !disabled && (
        <p className="text-xs text-amber-300">{partialWarning}</p>
      )}
      {error && !disabled && onRetry && <ErrorState message={error} onRetry={onRetry} />}
      {error && !disabled && !onRetry && (
        <p className="text-xs text-amber-300">{error}</p>
      )}
      {!loading && !disabled && children}
    </div>
  );
}

export function TabRefreshRow({ onRefresh }: { onRefresh: () => void }) {
  return (
    <div className="flex justify-end">
      <RetryButton onClick={onRefresh} />
    </div>
  );
}

export { StaleDataBadge };
