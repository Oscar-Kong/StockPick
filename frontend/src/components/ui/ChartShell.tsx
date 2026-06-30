"use client";

import clsx from "clsx";
import type { ReactNode } from "react";
import { ChartMount } from "@/components/ChartMount";
import type { ChartSummaryLine } from "@/lib/chartSummary";
import { useTranslation } from "@/lib/i18n";
import { AsyncStateShell, type AsyncState } from "./AsyncStateShell";
import { ChartTextSummary } from "./ChartTextSummary";

export type ChartShellState = Extract<AsyncState, "loading" | "empty" | "error" | "stale" | "success" | "partial">;

interface ChartShellProps {
  state: ChartShellState;
  children: ReactNode;
  className?: string;
  heightClassName?: string;
  latestDataDate?: string | null;
  isStale?: boolean;
  summaryLines?: ChartSummaryLine[];
  summarySrOnly?: boolean;
  emptyMessage?: string;
  errorMessage?: string | null;
  onRetry?: () => void;
  legend?: ReactNode;
  title?: string;
}

/** Shared chart container with mount deferral, async states, and text summary. */
export function ChartShell({
  state,
  children,
  className,
  heightClassName = "h-[min(24rem,50vh)]",
  latestDataDate,
  isStale,
  summaryLines = [],
  summarySrOnly = false,
  emptyMessage,
  errorMessage,
  onRetry,
  legend,
  title,
}: ChartShellProps) {
  const { t } = useTranslation();
  const shellState: AsyncState =
    state === "success" && isStale ? "stale" : state === "success" ? "success" : state;

  const staleMessage =
    isStale && latestDataDate
      ? `${t.common.staleData} · ${latestDataDate}`
      : isStale
        ? t.common.staleData
        : undefined;

  return (
    <figure className={clsx("chart-shell", className)}>
      {title && <figcaption className="sr-only">{title}</figcaption>}
      <AsyncStateShell
        state={shellState}
        emptyMessage={emptyMessage ?? t.analysis.chartNoData}
        errorMessage={errorMessage}
        staleMessage={staleMessage}
        onRetry={onRetry}
        skeletonLines={4}
        className="chart-shell__body"
      >
        {summaryLines.length > 0 && (
          <ChartTextSummary lines={summaryLines} srOnly={summarySrOnly} className="chart-shell__summary" />
        )}
        {latestDataDate && !isStale && (
          <p className="chart-shell__date text-xs text-tertiary">
            {t.analysis.latestBarLabel}: <span className="tabular-nums">{latestDataDate}</span>
          </p>
        )}
        <ChartMount className={clsx("chart-shell__mount", heightClassName)}>{children}</ChartMount>
        {legend && <div className="chart-shell__legend">{legend}</div>}
      </AsyncStateShell>
    </figure>
  );
}
