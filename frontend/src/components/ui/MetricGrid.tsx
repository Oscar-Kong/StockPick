"use client";

import clsx from "clsx";

interface MetricGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4;
  className?: string;
}

export function MetricGrid({ children, columns = 3, className }: MetricGridProps) {
  const cols =
    columns === 2
      ? "grid-cols-1 sm:grid-cols-2"
      : columns === 4
        ? "grid-cols-2 lg:grid-cols-4"
        : "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3";

  return <div className={clsx("grid gap-3", cols, className)}>{children}</div>;
}
