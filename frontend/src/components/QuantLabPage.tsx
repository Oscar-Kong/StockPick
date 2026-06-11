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
import { QuantLabEvidencePanel } from "@/components/quant-lab/QuantLabEvidencePanel";
import { QuantLabScanRelationshipPanel } from "@/components/product/QuantLabScanRelationshipPanel";
import { EvidenceToActionBoundary } from "@/components/product/EvidenceToActionBoundary";
import { PageHeader } from "@/components/ui/PageHeader";
import { ResearchWarning } from "@/components/ui/ResearchWarning";
import { useTranslation } from "@/lib/i18n";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback } from "react";

const TABS = [
  "factor-performance",
  "walk-forward",
  "predictions",
  "pairs",
  "data-quality",
  "model-admin",
] as const;

type QuantLabTab = (typeof TABS)[number];

function isQuantLabTab(value: string | null): value is QuantLabTab {
  return TABS.includes(value as QuantLabTab);
}

function QuantLabContent() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const tabParam = searchParams.get("tab");
  const tab: QuantLabTab = isQuantLabTab(tabParam) ? tabParam : "factor-performance";

  const setTab = useCallback(
    (next: QuantLabTab) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", next);
      router.replace(`/quant-lab?${params.toString()}`);
    },
    [router, searchParams]
  );

  const tabLabel: Record<QuantLabTab, string> = {
    "factor-performance": t.quantLab.tabFactorPerformance,
    "walk-forward": t.quantLab.tabWalkForward,
    predictions: t.quantLab.tabPredictions,
    pairs: t.quantLab.tabPairs,
    "data-quality": t.quantLab.tabDataQuality,
    "model-admin": t.quantLab.tabModelAdmin,
  };

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4">
      <PageHeader title={t.quantLab.title} subtitle={t.quantLab.subtitle} />
      <EvidenceToActionBoundary />
      <ResearchWarning message={t.quantLab.validationCopy} />

      <QuantLabScanRelationshipPanel />

      <QuantLabEvidencePanel onNavigateTab={setTab} />

      <AppTabBar aria-label={t.quantLab.tabsAria} className="overflow-x-auto">
        {TABS.map((key) => (
          <AppTabButton key={key} active={tab === key} onClick={() => setTab(key)}>
            {tabLabel[key]}
          </AppTabButton>
        ))}
      </AppTabBar>

      <div className="app-card p-5">
        {tab === "factor-performance" && <FactorPerformanceTab />}
        {tab === "walk-forward" && <WalkForwardTab />}
        {tab === "predictions" && <PredictionsTab />}
        {tab === "pairs" && <PairsTab />}
        {tab === "data-quality" && <DataQualityTab />}
        {tab === "model-admin" && <ModelAdminTab />}
      </div>
    </div>
  );
}

export function QuantLabPage() {
  const { t } = useTranslation();
  return (
    <Suspense fallback={<div className="px-4 py-6 text-sm text-zinc-500">{t.common.loading}</div>}>
      <QuantLabContent />
    </Suspense>
  );
}
