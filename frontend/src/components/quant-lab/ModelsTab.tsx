"use client";

import { QuantEquation } from "@/components/quant-lab/QuantEquation";
import { buildQuantLabHref } from "@/lib/quantLabNavigation";
import {
  QUANT_LAB_MODEL_CATALOG,
  QUANT_LAB_MODEL_IDS,
  type QuantLabModelId,
  type QuantLabModelStatus,
} from "@/lib/quantLabModels";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { useCallback, useState } from "react";

function statusTone(status: QuantLabModelStatus): string {
  if (status === "live") return "border-emerald-800/60 bg-emerald-950/30 text-emerald-300";
  if (status === "partial") return "border-amber-800/60 bg-amber-950/30 text-amber-200";
  return "border-zinc-700 bg-zinc-900/60 text-zinc-400";
}

type ModelCopy = {
  title: string;
  summary: string;
  usage: string;
  equations: Record<string, string>;
};

export function ModelsTab() {
  const { t } = useTranslation();
  const copy = t.quantLab.models;
  const [activeId, setActiveId] = useState<QuantLabModelId>("gbm");

  const modelCopy = useCallback(
    (id: QuantLabModelId): ModelCopy => copy[id as keyof typeof copy] as ModelCopy,
    [copy]
  );

  const active = QUANT_LAB_MODEL_CATALOG.find((m) => m.id === activeId)!;
  const activeText = modelCopy(activeId);
  const statusLabel: Record<QuantLabModelStatus, string> = {
    live: copy.statusLive,
    partial: copy.statusPartial,
    reference: copy.statusReference,
  };

  const linkHref =
    active.link?.href ??
    (active.link ? buildQuantLabHref(active.link.section, { legacyTab: active.link.legacyTab }) : null);

  return (
    <div className="space-y-4 text-sm">
      <header className="space-y-1">
        <h2 className="text-base font-semibold text-zinc-100">{copy.title}</h2>
        <p className="text-xs leading-relaxed text-zinc-400">{copy.subtitle}</p>
      </header>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <nav
          className="flex shrink-0 gap-2 overflow-x-auto lg:w-52 lg:flex-col lg:overflow-visible"
          aria-label={copy.navAria}
        >
          {QUANT_LAB_MODEL_IDS.map((id) => {
            const def = QUANT_LAB_MODEL_CATALOG.find((m) => m.id === id)!;
            const item = modelCopy(id);
            const selected = id === activeId;
            return (
              <button
                key={id}
                type="button"
                onClick={() => setActiveId(id)}
                className={`rounded-lg border px-3 py-2 text-left transition-colors ${
                  selected
                    ? "border-sky-800/70 bg-sky-950/40 text-zinc-100"
                    : "border-zinc-800 bg-zinc-950/40 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                }`}
              >
                <span className="block text-sm font-medium">{item.title}</span>
                <span
                  className={`mt-1 inline-block rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${statusTone(def.status)}`}
                >
                  {statusLabel[def.status]}
                </span>
              </button>
            );
          })}
        </nav>

        <article className="surface-card min-w-0 flex-1 p-4">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="text-lg font-semibold text-zinc-50">{activeText.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-zinc-400">{activeText.summary}</p>
            </div>
            <span
              className={`rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide ${statusTone(active.status)}`}
            >
              {statusLabel[active.status]}
            </span>
          </div>

          <section className="mb-4 rounded-lg border border-zinc-800/80 bg-zinc-950/50 px-3 py-2">
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">{copy.usageHeading}</p>
            <p className="mt-1 text-xs leading-relaxed text-zinc-300">{activeText.usage}</p>
            {linkHref && (
              <Link
                href={linkHref}
                className="mt-2 inline-block text-xs text-sky-400 hover:text-sky-300 hover:underline"
              >
                {copy.openRelated}
              </Link>
            )}
          </section>

          <section aria-labelledby="model-equations-heading">
            <h4 id="model-equations-heading" className="mb-3 text-sm font-semibold text-zinc-200">
              {copy.equationsHeading}
            </h4>
            <ol className="space-y-4">
              {active.equations.map((eq, index) => (
                <li
                  key={eq.id}
                  className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-3"
                >
                  <p className="mb-2 text-xs font-medium text-zinc-400">
                    {index + 1}. {activeText.equations[eq.id] ?? eq.id}
                  </p>
                  <QuantEquation tex={eq.tex} />
                </li>
              ))}
            </ol>
          </section>
        </article>
      </div>
    </div>
  );
}
