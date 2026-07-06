"use client";

import { DetailDrawer } from "@/components/ui/DetailDrawer";
import { QuantLabEvidencePanel } from "@/components/quant-lab/QuantLabEvidencePanel";
import { QuantLabScanRelationshipPanel } from "@/components/product/QuantLabScanRelationshipPanel";
import { EvidenceToActionBoundary } from "@/components/product/EvidenceToActionBoundary";
import type { Bucket } from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { useState } from "react";

type InfoDrawerTab = "evidence" | "scan" | "boundary";

interface QuantLabInfoDrawerProps {
  open: boolean;
  onClose: () => void;
  sleeve: Bucket;
  onNavigateEvidenceTab: (tab: string) => void;
}

export function QuantLabInfoDrawer({
  open,
  onClose,
  sleeve,
  onNavigateEvidenceTab,
}: QuantLabInfoDrawerProps) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<InfoDrawerTab>("evidence");

  const handleEvidenceNavigate = (tab: string) => {
    onNavigateEvidenceTab(tab);
    onClose();
  };

  return (
    <DetailDrawer
      open={open}
      title={t.quantLab.infoDrawerTitle}
      subtitle={t.quantLab.infoDrawerSubtitle}
      tabs={[
        { id: "evidence", label: t.quantLab.infoDrawerEvidenceTab },
        { id: "scan", label: t.quantLab.infoDrawerScanTab },
        { id: "boundary", label: t.quantLab.infoDrawerBoundaryTab },
      ]}
      activeTab={activeTab}
      onTabChange={(id) => setActiveTab(id as InfoDrawerTab)}
      onClose={onClose}
      className="quant-lab-info-drawer sm:max-w-xl"
    >
      {activeTab === "evidence" && (
        <QuantLabEvidencePanel sleeve={sleeve} onNavigateTab={handleEvidenceNavigate} />
      )}
      {activeTab === "scan" && <QuantLabScanRelationshipPanel />}
      {activeTab === "boundary" && <EvidenceToActionBoundary />}
    </DetailDrawer>
  );
}
