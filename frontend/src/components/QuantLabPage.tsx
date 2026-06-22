"use client";

import { AppTabBar, AppTabButton } from "@/components/AppTabs";
import { ExperimentStudio } from "@/components/quant-lab/ExperimentStudio";
import { IdeasBoardTab } from "@/components/quant-lab/IdeasBoardTab";
import { LegacyQuantLabTabs } from "@/components/quant-lab/LegacyQuantLabTabs";
import { ModelMonitorTab } from "@/components/quant-lab/ModelMonitorTab";
import { OverviewTab } from "@/components/quant-lab/OverviewTab";
import { ResultsTab } from "@/components/quant-lab/ResultsTab";
import { QuantLabEvidencePanel } from "@/components/quant-lab/QuantLabEvidencePanel";
import { QuantLabScanRelationshipPanel } from "@/components/product/QuantLabScanRelationshipPanel";
import { EvidenceToActionBoundary } from "@/components/product/EvidenceToActionBoundary";
import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import type { Bucket } from "@/lib/types";
import {
  buildQuantLabHref,
  isQuantLabLegacyTab,
  QUANT_LAB_SECTIONS,
  resolveQuantLabRoute,
  type QuantLabLegacyTab,
  type QuantLabSection,
} from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useState } from "react";

const PRIMARY_SECTIONS = QUANT_LAB_SECTIONS.filter((s) => s !== "legacy") as Exclude<
  QuantLabSection,
  "legacy"
>[];

function QuantLabContent() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { section, legacyTab } = resolveQuantLabRoute(searchParams);
  const [sleeve, setSleeve] = useState<Bucket>("penny");

  const setSection = useCallback(
    (next: QuantLabSection, opts?: { legacyTab?: QuantLabLegacyTab }) => {
      router.push(buildQuantLabHref(next, { legacyTab: opts?.legacyTab ?? legacyTab }));
    },
    [router, legacyTab]
  );

  const setLegacyTab = useCallback(
    (next: QuantLabLegacyTab) => {
      router.replace(buildQuantLabHref("legacy", { legacyTab: next }));
    },
    [router]
  );

  const sectionLabel: Record<Exclude<QuantLabSection, "legacy">, string> = {
    overview: t.quantLab.navOverview,
    ideas: t.quantLab.navIdeas,
    experiments: t.quantLab.navExperiments,
    results: t.quantLab.navResults,
    "model-monitor": t.quantLab.navModelMonitor,
  };

  const navigateEvidenceTab = useCallback(
    (tab: string) => {
      if (tab === "model-monitor" || tab === "data-quality" || tab === "model-admin") {
        setSection("model-monitor");
        return;
      }
      if (isQuantLabLegacyTab(tab)) {
        setSection("legacy", { legacyTab: tab });
      }
    },
    [setSection]
  );

  return (
    <PageContainer className="flex flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <PageHeader title={t.quantLab.title} subtitle={t.quantLab.subtitle} />
        <ResearchOnlyBadge tooltip={t.quantLab.researchOnlyWarning} />
      </div>

      <AppTabBar aria-label={t.quantLab.navAria} className="overflow-x-auto">
        {PRIMARY_SECTIONS.map((key) => (
          <AppTabButton key={key} active={section === key} onClick={() => setSection(key)}>
            {sectionLabel[key]}
          </AppTabButton>
        ))}
        <AppTabButton active={section === "legacy"} onClick={() => setSection("legacy")}>
          {t.quantLab.navLegacy}
        </AppTabButton>
      </AppTabBar>

      <div className="data-panel data-panel--padded min-h-[12rem]">
        {section === "overview" && (
          <OverviewTab
            sleeve={sleeve}
            onSleeveChange={setSleeve}
            onOpenIdeas={() => setSection("ideas")}
          />
        )}
        {section === "ideas" && <IdeasBoardTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "experiments" && <ExperimentStudio sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "results" && <ResultsTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "model-monitor" && <ModelMonitorTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "legacy" && <LegacyQuantLabTabs tab={legacyTab} onTabChange={setLegacyTab} />}
      </div>

      {section === "overview" && (
        <CollapsibleSection title={t.quantLab.evidenceTitle} defaultOpen={false}>
          <QuantLabEvidencePanel sleeve={sleeve} onNavigateTab={navigateEvidenceTab} />
        </CollapsibleSection>
      )}

      <CollapsibleSection title={t.product.quantLabAffectsScanTitle} defaultOpen={false}>
        <QuantLabScanRelationshipPanel />
      </CollapsibleSection>

      <EvidenceToActionBoundary />
    </PageContainer>
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
