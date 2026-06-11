"use client";

import clsx from "clsx";

interface LoadingSkeletonProps {
  className?: string;
  lines?: number;
  variant?: "lines" | "home";
}

export function LoadingSkeleton({ className, lines = 3, variant = "lines" }: LoadingSkeletonProps) {
  if (variant === "home") {
    return (
      <div className={clsx("animate-pulse space-y-5", className)} aria-hidden>
        <div className="app-card h-48 rounded-2xl bg-zinc-900/80" />
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="app-card h-20 bg-zinc-900/60" />
          ))}
        </div>
        <div className="grid gap-5 lg:grid-cols-12">
          <div className="app-card h-64 bg-zinc-900/60 lg:col-span-8" />
          <div className="app-card h-64 bg-zinc-900/60 lg:col-span-4" />
        </div>
      </div>
    );
  }

  return (
    <div className={clsx("animate-pulse space-y-2.5", className)} aria-hidden>
      {Array.from({ length: lines }).map((_, i) => (
        <div
          key={i}
          className="h-3.5 rounded-md bg-zinc-800/70"
          style={{ width: `${Math.max(40, 100 - i * 12)}%` }}
        />
      ))}
    </div>
  );
}
