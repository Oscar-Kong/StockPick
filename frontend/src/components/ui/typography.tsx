"use client";

import clsx from "clsx";

export function LabelCaps({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={clsx("text-label-caps", className)}>
      {children}
    </span>
  );
}

export function CurrencyText({
  children,
  className,
  tone = "default",
}: {
  children: React.ReactNode;
  className?: string;
  tone?: "default" | "positive" | "negative" | "muted";
}) {
  const tones = {
    default: "text-zinc-50",
    positive: "text-brand",
    negative: "text-negative",
    muted: "text-zinc-400",
  };
  return <span className={clsx("finance-value", tones[tone], className)}>{children}</span>;
}

export function PercentText({
  value,
  className,
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value == null || Number.isNaN(value)) {
    return <span className={clsx("finance-value text-tertiary", className)}>—</span>;
  }
  const tone = value >= 0 ? "text-brand" : "text-negative";
  const sign = value >= 0 ? "+" : "";
  return (
    <span className={clsx("finance-value text-sm font-medium", tone, className)}>
      {sign}
      {value.toFixed(1)}%
    </span>
  );
}

export function PageTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h1 className={clsx("page-title", className)}>{children}</h1>;
}

export function PageLead({ children, className }: { children: React.ReactNode; className?: string }) {
  return <p className={clsx("page-lead", className)}>{children}</p>;
}
