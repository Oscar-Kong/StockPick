"use client";

import clsx from "clsx";
import { MetricTile } from "./MetricTile";

interface SummaryStripProps {
  children: React.ReactNode;
  className?: string;
}

export function SummaryStrip({ children, className }: SummaryStripProps) {
  return <div className={clsx("summary-strip", className)}>{children}</div>;
}

interface SummaryStripItemProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "positive" | "negative" | "warning" | "muted";
  className?: string;
}

export function SummaryStripItem({ label,  value, hint, tone = "default", className }: SummaryStripItemProps) {
  return (
    <MetricTile
      label={label}
      value={value}
      hint={hint}
      tone={
        tone === "positive"
          ? "positive"
          : tone === "negative"
            ? "negative"
            : tone === "warning"
              ? "warning"
              : tone === "muted"
                ? "muted"
                : "default"
      }
      variant="summary"
      className={className}
    />
  );
}
