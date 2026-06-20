"use client";

import {
  DataQualityTab,
  FactorPerformanceTab,
  ModelAdminTab,
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
    "data-quality": t.quantLab.tabDataQuality,
    "model-admin": t.quantLab.tabModelAdmin,
  };

  return (
    <>
      <p className="text-xs text-zinc-500">{t.quantLab.legacyTabsHint}</p>
      <AppTabBar aria-label={t.quantLab.legacyTabsAria} className="overflow-x-auto">
        {LEGACY_TABS.map((key) => (
          <AppTabButton key={key} active={tab === key} onClick={() => onTabChange(key)}>
            {tabLabel[key]}
          </AppTabButton>
        ))}
      </AppTabBar>
      <div className="data-panel data-panel--padded min-h-[12rem]">
        {tab === "factor-performance" && <FactorPerformanceTab />}
        {tab === "walk-forward" && <WalkForwardTab />}
        {tab === "predictions" && <PredictionsTab />}
        {tab === "pairs" && <PairsTab />}
        {tab === "data-quality" && <DataQualityTab />}
        {tab === "model-admin" && <ModelAdminTab />}
      </div>
    </>
  );
}
