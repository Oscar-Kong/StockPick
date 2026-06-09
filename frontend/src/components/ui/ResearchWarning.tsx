"use client";

import clsx from "clsx";
import { useTranslation } from "@/lib/i18n";

interface ResearchWarningProps {
  message?: string;
  className?: string;
}

export function ResearchWarning({ message, className }: ResearchWarningProps) {
  const { t } = useTranslation();
  return (
    <p className={clsx("rounded-md border border-amber-900/50 bg-amber-950/30 px-3 py-2 text-xs text-amber-200/90", className)}>
      {message ?? t.quantLab.researchOnlyWarning}
    </p>
  );
}
