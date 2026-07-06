"use client";

import {
  FactorPerformanceTab,
  PairsTab,
  PredictionsTab,
  WalkForwardTab,
} from "@/components/quant-lab/QuantLabTabs";
import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import type { QuantLabLegacyTab } from "@/lib/quantLabNavigation";
import { LEGACY_TABS } from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";

interface LegacyQuantLabTabsProps {
  tab: QuantLabLegacyTab;
  onTabChange: (tab: QuantLabLegacyTab) => void;
}

export function LegacyQuantLabTabs({ tab, onTabChange }: LegacyQuantLabTabsProps) {
  const { t } = useTranslation();

  const tabLabel: Record<QuantLabLegacyTab, string> = {
    "factor-performance": t.quantLab.tabFactorPerformance,
    "walk-forward": t.quantLab.tabWalkForward,
    predictions: t.quantLab.tabPredictions,
    pairs: t.quantLab.tabPairs,
  };

  return (
    <div className="quant-lab-legacy space-y-3">
      <div className="quant-lab-legacy-banner" role="status">
        <p className="text-sm font-medium text-zinc-400">{t.quantLab.navLegacy}</p>
        <p className="mt-0.5 text-xs text-zinc-500">{t.quantLab.legacyTabsHint}</p>
      </div>
      <AppTabBar aria-label={t.quantLab.legacyTabsAria} className="overflow-x-auto quant-lab-legacy-tabs">
        {LEGACY_TABS.map((key) => (
          <AppTabButton key={key} active={tab === key} onClick={() => onTabChange(key)}>
            {tabLabel[key]}
          </AppTabButton>
        ))}
      </AppTabBar>
      <div className="min-h-0">
        {tab === "factor-performance" && <FactorPerformanceTab />}
        {tab === "walk-forward" && <WalkForwardTab />}
        {tab === "predictions" && <PredictionsTab />}
        {tab === "pairs" && <PairsTab />}
      </div>
    </div>
  );
}
