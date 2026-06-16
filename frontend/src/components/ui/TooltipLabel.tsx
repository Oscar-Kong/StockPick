"use client";

import clsx from "clsx";

interface TooltipLabelProps {
  label: string;
  tooltip: string;
  className?: string;
}

export function TooltipLabel({ label, tooltip, className }: TooltipLabelProps) {
  return (
    <span className={clsx("inline-flex items-center gap-1", className)}>
      <span>{label}</span>
      <span
        className="cursor-help rounded-full border border-zinc-700 px-1 text-xs leading-none text-zinc-500"
        title={tooltip}
        aria-label={tooltip}
      >
        ?
      </span>
    </span>
  );
}
