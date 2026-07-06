"use client";

import { ProductFlowDiagram } from "./ProductFlowDiagram";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { useTranslation } from "@/lib/i18n";

export function QuantLabScanRelationshipPanel() {
  const { t } = useTranslation();
  return (
    <GlassPanel variant="compact" className="mb-4 space-y-3">
      <h2 className="text-sm font-semibold text-foreground">{t.product.quantLabAffectsScanTitle}</h2>
      <p className="text-xs leading-relaxed text-secondary">{t.product.quantLabAffectsScanCopy}</p>
      <ProductFlowDiagram />
    </GlassPanel>
  );
}
