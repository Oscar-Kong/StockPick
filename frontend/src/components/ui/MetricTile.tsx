"use client";

import clsx from "clsx";
import { TooltipLabel } from "./TooltipLabel";

export type MetricTileVariant = "compact" | "summary" | "card" | "inline" | "emphasized";

export type MetricTileTone = "default" | "positive" | "negative" | "warning" | "muted" | "primary";

const VALUE_TONE: Record<MetricTileTone, string> = {
  default: "text-foreground",
  positive: "text-positive",
  negative: "text-negative",
  warning: "text-hold",
  muted: "text-tertiary",
  primary: "text-buy",
};

const SUMMARY_TONE: Record<"default" | "positive" | "negative" | "warning" | "muted", string> = {
  default: "summary-strip__value--default",
  positive: "summary-strip__value--positive",
  negative: "summary-strip__value--negative",
  warning: "summary-strip__value--warning",
  muted: "summary-strip__value--muted",
};

interface MetricTileProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tooltip?: string;
  change?: React.ReactNode;
  tone?: MetricTileTone;
  variant?: MetricTileVariant;
  action?: React.ReactNode;
  className?: string;
  truncateTitle?: string;
}

/** Unified metric presentation for strips, grids, cards, and inline stats. */
export function MetricTile({
  label,
  value,
  hint,
  tooltip,
  change,
  tone = "default",
  variant = "compact",
  action,
  className,
  truncateTitle,
}: MetricTileProps) {
  if (variant === "summary") {
    const summaryTone =
      tone === "positive" || tone === "negative" || tone === "warning" || tone === "muted"
        ? tone
        : "default";
    return (
      <div className={clsx("summary-strip__item metric-tile metric-tile--summary", className)}>
        <span className="summary-strip__label">{label}</span>
        <span className={clsx("summary-strip__value finance-value", SUMMARY_TONE[summaryTone])}>
          {value}
        </span>
        {hint && <span className="summary-strip__hint">{hint}</span>}
        {action}
      </div>
    );
  }

  if (variant === "compact") {
    return (
      <dl className={clsx("stat-tile metric-tile metric-tile--compact", className)}>
        <dt className="stat-tile__label truncate">
          {tooltip ? <TooltipLabel label={label} tooltip={tooltip} /> : label}
        </dt>
        <dd
          className={clsx("stat-tile__value finance-value", VALUE_TONE[tone], truncateTitle && "truncate")}
          title={truncateTitle}
        >
          {value}
          {change != null && <span className="metric-tile__change ml-1">{change}</span>}
        </dd>
        {hint && <dd className="stat-tile__hint">{hint}</dd>}
        {action}
      </dl>
    );
  }

  const valueSize =
    variant === "emphasized" ? "metric-tile__value--emphasized" : variant === "inline" ? "text-sm" : "";

  return (
    <div
      className={clsx(
        "metric-tile",
        variant === "card" && "metric-tile--card",
        variant === "inline" && "metric-tile--inline",
        variant === "emphasized" && "metric-tile--emphasized",
        className
      )}
    >
      <p className="metric-tile__label">
        {tooltip ? <TooltipLabel label={label} tooltip={tooltip} /> : label}
      </p>
      <p className={clsx("metric-tile__value finance-value", VALUE_TONE[tone], valueSize)}>
        {value}
        {change != null && <span className="metric-tile__change ml-1">{change}</span>}
      </p>
      {hint && <p className="metric-tile__hint">{hint}</p>}
      {action}
    </div>
  );
}
