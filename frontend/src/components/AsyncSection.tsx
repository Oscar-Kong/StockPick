"use client";

import clsx from "clsx";

type AsyncSectionState = "idle" | "loading" | "error" | "empty" | "ready";

interface AsyncSectionProps {
  state: AsyncSectionState;
  loadingText?: string;
  errorText?: string | null;
  emptyText?: string;
  children: React.ReactNode;
  className?: string;
}

export function AsyncSection({
  state,
  loadingText = "Loading…",
  errorText,
  emptyText = "No data.",
  children,
  className,
}: AsyncSectionProps) {
  if (state === "loading") {
    return <p className={clsx("text-xs text-zinc-500", className)}>{loadingText}</p>;
  }
  if (state === "error" && errorText) {
    return <p className={clsx("text-xs text-red-400/90", className)}>{errorText}</p>;
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
