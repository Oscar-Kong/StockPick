"use client";

import type { ResearchReliabilityScore, ResearchReliabilityStatus } from "@/lib/researchReliability";
import { translateReliabilityList } from "@/lib/researchReliability";
import { useTranslation } from "@/lib/i18n";

const STATUS_STYLES: Record<ResearchReliabilityStatus, string> = {
  reliable: "border-emerald-900/50 bg-emerald-950/40 text-emerald-200",
  usable_with_warnings: "border-amber-900/50 bg-amber-950/40 text-amber-200",
  weak_evidence: "border-orange-900/50 bg-orange-950/40 text-orange-200",
  insufficient_data: "border-zinc-700 bg-zinc-900/60 text-zinc-400",
  stale: "border-amber-900/50 bg-amber-950/40 text-amber-200",
  disabled: "border-zinc-700 bg-zinc-950/60 text-zinc-500",
  research_only: "border-sky-900/40 bg-sky-950/30 text-sky-200/90",
};

interface ResearchReliabilityCardProps {
  score: ResearchReliabilityScore;
  /** Max reason lines shown before "show more" is implied by truncation. */
  maxReasons?: number;
}

export function ResearchReliabilityCard({ score, maxReasons = 3 }: ResearchReliabilityCardProps) {
  const { t } = useTranslation();
  const statusLabels: Record<ResearchReliabilityStatus, string> = {
    reliable: t.reliability.statusReliable,
    usable_with_warnings: t.reliability.statusUsableWithWarnings,
    weak_evidence: t.reliability.statusWeakEvidence,
    insufficient_data: t.reliability.statusInsufficientData,
    stale: t.reliability.statusStale,
    disabled: t.reliability.statusDisabled,
    research_only: t.reliability.statusResearchOnly,
  };

  const reasons = translateReliabilityList(score.reasons, "reasons", t);
  const warnings = translateReliabilityList(score.warnings, "warnings", t);
  const blockers = translateReliabilityList(score.blockers, "blockers", t);
  const nextAction = translateReliabilityList([score.suggested_next_action], "actions", t)[0];

  return (
    <section
      className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 space-y-2"
      data-testid="research-reliability-card"
      aria-label={t.reliability.cardTitle}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
          {t.reliability.cardTitle}
        </h4>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium uppercase tracking-wide ${STATUS_STYLES[score.status]}`}
            data-testid="research-reliability-badge"
          >
            {statusLabels[score.status]}
          </span>
          <span
            className="text-sm font-semibold tabular-nums text-zinc-200"
            data-testid="research-reliability-score"
          >
            {score.score_0_to_100}
          </span>
        </div>
      </div>

      {reasons.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase text-zinc-500">{t.reliability.reasonsLabel}</p>
          <ul className="mt-1 list-inside list-disc text-xs text-zinc-400">
            {reasons.slice(0, maxReasons).map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase text-amber-600/80">{t.reliability.warningsLabel}</p>
          <ul className="mt-1 list-inside list-disc text-xs text-amber-200/90">
            {warnings.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      {blockers.length > 0 && (
        <div>
          <p className="text-xs font-medium uppercase text-rose-600/80">{t.reliability.blockersLabel}</p>
          <ul className="mt-1 list-inside list-disc text-xs text-rose-200/90">
            {blockers.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <p className="text-xs text-zinc-500">
        <span className="font-medium text-zinc-400">{t.reliability.nextActionLabel}: </span>
        {nextAction}
      </p>
    </section>
  );
}
