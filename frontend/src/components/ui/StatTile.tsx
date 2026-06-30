"use client";

import { MetricTile } from "./MetricTile";

interface StatTileProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tooltip?: string;
  className?: string;
  truncateTitle?: string;
}

/** Compact labeled stat — wraps MetricTile (compact variant). */
export function StatTile({ label, value, hint, tooltip, className, truncateTitle }: StatTileProps) {
  return (
    <MetricTile
      label={label}
      value={value}
      hint={hint}
      tooltip={tooltip}
      className={className}
      truncateTitle={truncateTitle}
      variant="compact"
    />
  );
}
