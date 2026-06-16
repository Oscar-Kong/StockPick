"use client";

import clsx from "clsx";

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

const TONE: Record<NonNullable<SummaryStripItemProps["tone"]>, string> = {
  default: "summary-strip__value--default",
  positive: "summary-strip__value--positive",
  negative: "summary-strip__value--negative",
  warning: "summary-strip__value--warning",
  muted: "summary-strip__value--muted",
};

export function SummaryStripItem({ label, value, hint, tone = "default", className }: SummaryStripItemProps) {
  return (
    <div className={clsx("summary-strip__item", className)}>
      <span className="summary-strip__label">{label}</span>
      <span className={clsx("summary-strip__value finance-value", TONE[tone])}>{value}</span>
      {hint && <span className="summary-strip__hint">{hint}</span>}
    </div>
  );
}
