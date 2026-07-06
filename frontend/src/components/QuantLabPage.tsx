"use client";

import { ExperimentStudio } from "@/components/quant-lab/ExperimentStudio";
import { IdeasBoardTab } from "@/components/quant-lab/IdeasBoardTab";
import { LegacyQuantLabTabs } from "@/components/quant-lab/LegacyQuantLabTabs";
import { FactorDiscoveryWorkspace } from "@/components/quant-lab/factor-discovery/FactorDiscoveryWorkspace";
import { ModelMonitorTab } from "@/components/quant-lab/ModelMonitorTab";
import { OverviewTab } from "@/components/quant-lab/OverviewTab";
import { QuantLabInfoDrawer } from "@/components/quant-lab/QuantLabInfoDrawer";
import { QuantLabSectionNav } from "@/components/quant-lab/QuantLabSectionNav";
import { ResultsTab } from "@/components/quant-lab/ResultsTab";
import { BucketSelect } from "@/components/quant-lab/QuantLabTabShell";
import { DataPanel } from "@/components/ui/DataPanel";
import { PageContainer } from "@/components/ui/PageContainer";
import { PageHeader } from "@/components/ui/PageHeader";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { ResearchOnlyBadge } from "@/components/ui/ResearchOnlyBadge";
import type { Bucket } from "@/lib/types";
import {
  buildQuantLabHref,
  isQuantLabLegacyTab,
  QUANT_LAB_SLEEVE_SECTIONS,
  resolveQuantLabRoute,
  type QuantLabLegacyTab,
  type QuantLabPrimarySection,
  type QuantLabSection,
} from "@/lib/quantLabNavigation";
import { useTranslation } from "@/lib/i18n";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

function QuantLabContent() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const { section, legacyTab } = resolveQuantLabRoute(searchParams);
  const [sleeve, setSleeve] = useState<Bucket>("penny");
  const [infoOpen, setInfoOpen] = useState(false);

  const setSection = (next: QuantLabSection, opts?: { legacyTab?: QuantLabLegacyTab }) => {
    router.push(buildQuantLabHref(next, { legacyTab: opts?.legacyTab ?? legacyTab }));
  };

  const setLegacyTab = (next: QuantLabLegacyTab) => {
    router.replace(buildQuantLabHref("legacy", { legacyTab: next }));
  };

  const sectionHint: Record<QuantLabPrimarySection, string> = {
    overview: t.quantLab.sectionHintOverview,
    ideas: t.quantLab.sectionHintIdeas,
    experiments: t.quantLab.sectionHintExperiments,
    "factor-discovery": t.quantLab.sectionHintFactorDiscovery,
    results: t.quantLab.sectionHintResults,
    "model-monitor": t.quantLab.sectionHintModelMonitor,
  };

  const navigateEvidenceTab = (tab: string) => {
    if (tab === "model-monitor" || tab === "data-quality" || tab === "model-admin") {
      setSection("model-monitor");
      return;
    }
    if (isQuantLabLegacyTab(tab)) {
      setSection("legacy", { legacyTab: tab });
    }
  };

  const showSleeve = (QUANT_LAB_SLEEVE_SECTIONS as readonly string[]).includes(section);

  return (
    <PageContainer className="quant-lab-page flex flex-1 flex-col gap-2">
      <header className="quant-lab-header">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <PageHeader title={t.quantLab.title} subtitle={t.quantLab.subtitle} />
          <div className="quant-lab-command-bar">
            {showSleeve && (
              <BucketSelect label={t.common.bucket} value={sleeve} onChange={(v) => setSleeve(v as Bucket)} />
            )}
            <button
              type="button"
              className="quant-lab-info-btn"
              data-testid="quant-lab-guide-btn"
              onClick={() => setInfoOpen(true)}
              aria-label={t.quantLab.infoDrawerButton}
            >
              {t.quantLab.infoDrawerButton}
            </button>
            <ResearchOnlyBadge tooltip={t.quantLab.researchOnlyWarning} />
          </div>
        </div>
        {section !== "legacy" && (
          <p className="quant-lab-section-hint" role="status">
            {sectionHint[section as QuantLabPrimarySection]}
          </p>
        )}
      </header>

      <QuantLabSectionNav section={section} onSectionChange={setSection} />

      <DataPanel className="quant-lab-workspace min-h-0">
        {section === "overview" && (
          <OverviewTab sleeve={sleeve} onOpenIdeas={() => setSection("ideas")} />
        )}
        {section === "ideas" && <IdeasBoardTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "experiments" && <ExperimentStudio sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "factor-discovery" && <FactorDiscoveryWorkspace />}
        {section === "results" && <ResultsTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "model-monitor" && <ModelMonitorTab sleeve={sleeve} onSleeveChange={setSleeve} />}
        {section === "legacy" && <LegacyQuantLabTabs tab={legacyTab} onTabChange={setLegacyTab} />}
      </DataPanel>

      <QuantLabInfoDrawer
        open={infoOpen}
        onClose={() => setInfoOpen(false)}
        sleeve={sleeve}
        onNavigateEvidenceTab={navigateEvidenceTab}
      />
    </PageContainer>
  );
}

export function QuantLabPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={4} className="px-4 py-6" />}>
      <QuantLabContent />
    </Suspense>
  );
}
