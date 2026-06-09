"use client";

import clsx from "clsx";

interface LoadingSkeletonProps {
  className?: string;
  lines?: number;
}

export function LoadingSkeleton({ className, lines = 3 }: LoadingSkeletonProps) {
  return (
    <div className={clsx("animate-pulse space-y-2", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3 rounded bg-zinc-800/80"
          style={{ width: `${Math.max(40, 100 - i * 12)}%` }}
        />
      ))}
    </div>
  );
}
