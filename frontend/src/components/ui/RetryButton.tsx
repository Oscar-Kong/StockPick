"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface RetryButtonProps {
  onClick: () => void;
  className?: string;
  label?: string;
}

export function RetryButton({ onClick, className, label }: RetryButtonProps) {
  const { t } = useTranslation();
  return (
    <button type="button" onClick={onClick} className={clsx("btn-ghost px-2 py-1 text-xs", className)}>
      {label ?? t.common.retry}
    </button>
  );
}
