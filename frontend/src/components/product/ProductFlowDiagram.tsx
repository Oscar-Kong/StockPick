"use client";

import { useTranslation } from "@/lib/i18n";

export function ProductFlowDiagram() {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4 text-xs text-zinc-400">
      <p className="mb-2 font-medium text-zinc-300">{t.product.flowTitle}</p>
      <div className="space-y-2 font-mono text-sm leading-relaxed">
        <p>{t.product.flowProduction}</p>
        <p className="pl-4 text-zinc-500">{t.product.flowProductionDetail}</p>
        <p className="text-sky-200/80">{t.product.flowValidation}</p>
        <p className="pl-4 text-zinc-500">{t.product.flowValidationDetail}</p>
      </div>
    </div>
  );
}
