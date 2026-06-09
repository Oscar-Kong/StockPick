"use client";

import clsx from "clsx";

interface EmptyStateProps {
  title?: string;
  message: string;
  className?: string;
  action?: React.ReactNode;
}

export function EmptyState({ title, message, className, action }: EmptyStateProps) {
  return (
    <div className={clsx("rounded-lg border border-dashed border-zinc-800 px-4 py-6 text-center", className)}>
      {title && <p className="text-sm font-medium text-zinc-300">{title}</p>}
      <p className={clsx("text-xs text-zinc-500", title && "mt-1")}>{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
