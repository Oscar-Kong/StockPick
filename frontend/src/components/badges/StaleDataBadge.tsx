"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface StaleDataBadgeProps {
  asOf?: string | null;
  className?: string;
}

export function StaleDataBadge({ asOf, className }: StaleDataBadgeProps) {
  const { t } = useTranslation();
  return (
    <span
      className={clsx(
        "chip border-amber-600/40 bg-amber-950/30 px-1.5 py-0.5 text-[10px] font-medium text-amber-200",
        className
      )}
      title={asOf ? `${t.common.staleData}: ${asOf}` : t.common.staleData}
    >
      {t.common.staleData}
    </span>
  );
}
