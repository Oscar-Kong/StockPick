"use client";

import type { ChartSummaryLine } from "@/lib/chartSummary";
import clsx from "clsx";

interface ChartTextSummaryProps {
  lines: ChartSummaryLine[];
  className?: string;
  /** When true, summary is visible only to screen readers */
  srOnly?: boolean;
}

/** Compact key-value chart summary for accessibility and quick scanning. */
export function ChartTextSummary({ lines, className, srOnly = false }: ChartTextSummaryProps) {
  if (!lines.length) return null;

  return (
    <p
      className={clsx(
        "chart-text-summary text-xs text-secondary",
        srOnly && "sr-only",
        className
      )}
    >
      {lines.map((line, i) => (
        <span key={`${line.label}-${i}`}>
          {i > 0 && <span aria-hidden> · </span>}
          <span className="text-tertiary">{line.label}:</span>{" "}
          <span className="tabular-nums text-zinc-200">{line.value}</span>
        </span>
      ))}
    </p>
  );
}
