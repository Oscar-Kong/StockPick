"use client";

import clsx from "clsx";
import { TooltipLabel } from "./TooltipLabel";

interface StatTileProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tooltip?: string;
  className?: string;
  /** When set, long single-line values truncate with a native tooltip. */
  truncateTitle?: string;
}

/** Compact labeled stat for grids — label on top, value below. */
export function StatTile({ label, value, hint, tooltip, className, truncateTitle }: StatTileProps) {
  return (
    <dl className={clsx("stat-tile", className)}>
      <dt className="stat-tile__label truncate">
        {tooltip ? <TooltipLabel label={label} tooltip={tooltip} /> : label}
      </dt>
      <dd
        className={clsx("stat-tile__value finance-value", truncateTitle && "truncate")}
        title={truncateTitle}
      >
        {value}
      </dd>
      {hint && <dd className="stat-tile__hint">{hint}</dd>}
    </dl>
  );
}
