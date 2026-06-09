"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface ResearchOnlyBadgeProps {
  tooltip?: string;
  className?: string;
}

export function ResearchOnlyBadge({ tooltip, className }: ResearchOnlyBadgeProps) {
  const { t } = useTranslation();
  const title = tooltip ?? t.product.researchOnlyTooltip;
  return (
    <span
      className={clsx(
        "inline-flex rounded-full border border-sky-900/50 bg-sky-950/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-sky-200/90",
        className
      )}
      title={title}
      aria-label={title}
    >
      {t.product.researchOnlyBadge}
    </span>
  );
}
