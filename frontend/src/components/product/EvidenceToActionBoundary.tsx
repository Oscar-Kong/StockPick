"use client";

import { useTranslation } from "@/lib/i18n";

/** Boundary between validation evidence and live scan scoring — no silent apply. */
export function EvidenceToActionBoundary() {
  const { t } = useTranslation();
  return (
    <aside
      className="mb-4 rounded-lg border border-zinc-800 bg-zinc-950/60 px-4 py-3 text-xs text-zinc-400"
      data-testid="evidence-to-action-boundary"
    >
      <p className="font-medium text-zinc-300">{t.reliability.evidenceBoundaryTitle}</p>
      <p className="mt-1 leading-relaxed">{t.reliability.evidenceBoundaryCopy}</p>
    </aside>
  );
}
