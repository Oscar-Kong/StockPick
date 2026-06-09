"use client";

import { ProductFlowDiagram } from "./ProductFlowDiagram";
import { useTranslation } from "@/lib/i18n";

export function QuantLabScanRelationshipPanel() {
  const { t } = useTranslation();
  return (
    <section className="mb-4 space-y-3 rounded-lg border border-zinc-800 bg-zinc-950/40 p-4">
      <h2 className="text-sm font-semibold text-zinc-200">{t.product.quantLabAffectsScanTitle}</h2>
      <p className="text-xs leading-relaxed text-zinc-500">{t.product.quantLabAffectsScanCopy}</p>
      <ProductFlowDiagram />
    </section>
  );
}
