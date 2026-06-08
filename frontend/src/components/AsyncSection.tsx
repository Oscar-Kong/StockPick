"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

type AsyncSectionState = "idle" | "loading" | "error" | "empty" | "ready";

interface AsyncSectionProps {
  state: AsyncSectionState;
  loadingText?: string;
  errorText?: string | null;
  emptyText?: string;
  onRetry?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function AsyncSection({
  state,
  loadingText = "Loading…",
  errorText,
  emptyText = "No data.",
  onRetry,
  children,
  className,
}: AsyncSectionProps) {
  const { t } = useTranslation();
  if (state === "loading") {
    return <p className={clsx("text-xs text-zinc-500", className)}>{loadingText}</p>;
  }
  if (state === "error" && errorText) {
    return (
      <div className={clsx("space-y-2", className)}>
        <p className="text-xs text-red-400/90">{errorText}</p>
        {onRetry && (
          <button type="button" onClick={onRetry} className="btn-ghost px-2 py-1 text-xs">
            {t.common.retry}
          </button>
        )}
      </div>
    );
  }
  if (state === "empty") {
    return <p className={clsx("text-xs text-zinc-500", className)}>{emptyText}</p>;
  }
  if (state !== "ready") {
    return null;
  }
  return <div className={className}>{children}</div>;
}

export function fmtPct(value: number | null | undefined, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toFixed(digits);
}
