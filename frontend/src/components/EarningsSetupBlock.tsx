"use client";

import { useTranslation } from "@/lib/i18n";
import type { V2ScoreResponse } from "@/lib/types";

export function EarningsSetupBlock({ setup }: { setup: Record<string, unknown> }) {
  const { t } = useTranslation();
  const details = (setup.details as Record<string, unknown>) || {};
  return (
    <div className="space-y-1 rounded-lg border border-zinc-800 bg-zinc-950/50 p-3 text-xs text-zinc-300">
      <p className="font-medium text-zinc-200">{t.quant.earningsSetup}</p>
      <div className="grid grid-cols-2 gap-1 tabular-nums">
        <span className="text-zinc-500">{t.report.nextEarnings}</span>
        <span>{setup.next_earnings_days != null ? `${setup.next_earnings_days}d` : "—"}</span>
        <span className="text-zinc-500">{t.quant.epsRev30d}</span>
        <span>{setup.eps_revision_30d_pct != null ? `${setup.eps_revision_30d_pct}%` : "—"}</span>
        <span className="text-zinc-500">{t.quant.revRev30d}</span>
        <span>{setup.revenue_revision_30d_pct != null ? `${setup.revenue_revision_30d_pct}%` : "—"}</span>
        <span className="text-zinc-500">{t.quant.upDown}</span>
        <span>
          {String(setup.analyst_upgrades ?? 0)} / {String(setup.analyst_downgrades ?? 0)}
        </span>
        <span className="text-zinc-500">{t.quant.drift5d20d}</span>
        <span>
          {details.post_earnings_drift_5d_pct != null ? `${details.post_earnings_drift_5d_pct}%` : "—"} /{" "}
          {details.post_earnings_drift_20d_pct != null ? `${details.post_earnings_drift_20d_pct}%` : "—"}
        </span>
        <span className="text-zinc-500">{t.quant.catalyst}</span>
        <span>{setup.catalyst_score != null ? String(setup.catalyst_score) : "—"}</span>
      </div>
      {typeof setup.risk_note === "string" && setup.risk_note && (
        <p className="text-amber-300/90">{setup.risk_note}</p>
      )}
    </div>
  );
}

export function EarningsFromScore({ score }: { score: V2ScoreResponse }) {
  if (!score.earnings_setup || !Object.keys(score.earnings_setup).length) return null;
  return <EarningsSetupBlock setup={score.earnings_setup} />;
}
