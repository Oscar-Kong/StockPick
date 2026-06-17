"use client";

import { PortfolioAllocationPanel } from "@/components/PortfolioAllocationPanel";
import { ResearchWarning } from "@/components/ui/ResearchWarning";
import { useTranslation } from "@/lib/i18n";

interface PortfolioAdvancedTabProps {
  symbols: string[];
}

export function PortfolioAdvancedTab({ symbols }: PortfolioAdvancedTabProps) {
  const { t } = useTranslation();

  return (
    <div className="space-y-4">
      <ResearchWarning message={t.portfolio.advancedExperimentalWarning} />
      <p className="text-xs text-zinc-500">{t.portfolio.advancedHint}</p>
      <PortfolioAllocationPanel symbols={symbols} experimental />
    </div>
  );
}
