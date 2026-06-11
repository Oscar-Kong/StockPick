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
    <div className={clsx("app-card app-card--ghost px-6 py-10 text-center", className)}>
      {title && <p className="text-base font-semibold text-zinc-200">{title}</p>}
      <p className={clsx("text-sm leading-relaxed text-zinc-500", title && "mt-2")}>{message}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
