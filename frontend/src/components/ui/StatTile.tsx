"use client";

import clsx from "clsx";
import { TooltipLabel } from "./TooltipLabel";

interface StatTileProps {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tooltip?: string;
  className?: string;
}

/** Compact labeled stat for grids — label on top, value below. */
export function StatTile({ label, value, hint, tooltip, className }: StatTileProps) {
  return (
    <dl className={clsx("min-w-0 rounded-lg border border-zinc-800/80 bg-zinc-950/30 px-3.5 py-3", className)}>
      <dt className="text-[11px] font-medium uppercase tracking-wide text-zinc-500">
        {tooltip ? <TooltipLabel label={label} tooltip={tooltip} /> : label}
      </dt>
      <dd className="mt-1.5 text-sm font-medium text-zinc-100">{value}</dd>
      {hint && <dd className="mt-1 text-xs leading-relaxed text-zinc-500">{hint}</dd>}
    </dl>
  );
}
