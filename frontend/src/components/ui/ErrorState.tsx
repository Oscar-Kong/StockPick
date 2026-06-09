"use client";

import clsx from "clsx";
import { RetryButton } from "./RetryButton";

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <div className={clsx("space-y-2 rounded-lg border border-red-900/40 bg-red-950/20 px-4 py-3", className)}>
      <p className="text-xs text-red-300/90">{message}</p>
      {onRetry && <RetryButton onClick={onRetry} />}
    </div>
  );
}
