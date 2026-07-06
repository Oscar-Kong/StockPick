"use client";

import { GlassPanel } from "@/components/ui/GlassPanel";
import { useTranslation } from "@/lib/i18n";

/** Boundary between validation evidence and live scan scoring — no silent apply. */
export function EvidenceToActionBoundary() {
  const { t } = useTranslation();
  return (
    <GlassPanel
      as="aside"
      variant="compact"
      className="mb-4 text-xs text-secondary"
      data-testid="evidence-to-action-boundary"
    >
      <p className="font-medium text-foreground">{t.reliability.evidenceBoundaryTitle}</p>
      <p className="mt-1 leading-relaxed">{t.reliability.evidenceBoundaryCopy}</p>
    </GlassPanel>
  );
}
