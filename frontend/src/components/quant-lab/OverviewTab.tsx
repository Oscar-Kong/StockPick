"use client";

import {
  generateResearchIdeas,
  getResearchOverview,
  postForwardLabelsJob,
  postIcPanelJob,
  postResearchRunsBackfill,
  postResolveOutcomesJob,
  enqueueV2Job,
} from "@/lib/api";
import { parseApiError } from "@/lib/apiError";
import type { Bucket, ResearchOverviewResponse } from "@/lib/types";
import { useTranslation, useTRef } from "@/lib/i18n";
import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@/components/ui/ErrorState";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { LoadingSkeleton } from "@/components/ui/LoadingSkeleton";
import { MetricTile, type MetricTileTone } from "@/components/ui/MetricTile";

function confidenceTone(status: string): MetricTileTone {
  if (status === "reliable") return "positive";
  if (status === "usable_with_warnings") return "warning";
  if (status === "insufficient_data") return "negative";
  return "default";
}

function freshnessTone(freshness: string): MetricTileTone {
  if (freshness === "fresh") return "positive";
  if (freshness === "stale" || freshness === "degraded") return "warning";
  if (freshness === "critical") return "negative";
  return "muted";
}

async function runMaintenanceAction(actionId: string): Promise<void> {
  switch (actionId) {
    case "ic_panel":
      await postIcPanelJob();
      break;
    case "forward_labels":
      await postForwardLabelsJob();
      break;
    case "resolve_outcomes":
      await postResolveOutcomesJob();
      break;
    case "quant_daily_jobs":
      await enqueueV2Job("quant_daily_jobs");
      break;
    case "refresh_evidence":
      await postResearchRunsBackfill(100);
      break;
    default:
      break;
  }
}

interface OverviewTabProps {
  sleeve: Bucket;
  onOpenIdeas: () => void;
}

export function OverviewTab({ sleeve, onOpenIdeas }: OverviewTabProps) {
  const { t } = useTranslation();
  const tRef = useTRef();
  const [data, setData] = useState<ResearchOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState<string | null>(null);
  const [generateBusy, setGenerateBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await getResearchOverview(sleeve));
    } catch (e) {
      setData(null);
      setError(parseApiError(e, tRef.current.quantLab.loadFailed));
    } finally {
      setLoading(false);
    }
  }, [sleeve, tRef]);

  useEffect(() => {
    void load();
  }, [load]);

  const onMaintenance = async (actionId: string) => {
    setActionBusy(actionId);
    try {
      await runMaintenanceAction(actionId);
      await load();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setActionBusy(null);
    }
  };

  const onGenerateIdeas = async () => {
    setGenerateBusy(true);
    try {
      await generateResearchIdeas({ sleeve, limit: 8 });
      await load();
      onOpenIdeas();
    } catch (e) {
      setError(parseApiError(e, tRef.current.quantLab.runFailed));
    } finally {
      setGenerateBusy(false);
    }
  };

  if (loading) return <LoadingSkeleton lines={6} />;
  if (error && !data) return <ErrorState message={error} onRetry={() => void load()} />;

  const overview = data!;

  return (
    <div className="space-y-4 text-sm">
      {error && <p className="text-xs text-amber-300">{error}</p>}

      <GlassPanel variant="hero" aria-label={t.quantLab.navOverview}>
        <div className="quant-lab-overview-kpis">
          <MetricTile
            variant="card"
            label={t.quantLab.overviewConfidence}
            value={`${overview.research_confidence_score}/100`}
            hint={overview.research_confidence_status.replace(/_/g, " ")}
            tone={confidenceTone(overview.research_confidence_status)}
          />
          <MetricTile
            variant="card"
            label={t.quantLab.overviewFreshness}
            value={overview.data_freshness}
            tone={freshnessTone(overview.data_freshness)}
          />
          <MetricTile
            variant="card"
            label={t.quantLab.overviewVersions}
            value={overview.strategy_version}
            hint={overview.factor_model_version}
          />
          <MetricTile
            variant="card"
            label={t.quantLab.overviewPredictions}
            value={overview.predictions_resolved}
            hint={`${overview.predictions_unresolved} ${t.quantLab.overviewUnresolved}`}
          />
        </div>
      </GlassPanel>

      {overview.major_warnings.length > 0 && (
        <section className="rounded-lg border border-amber-900/50 bg-amber-950/20 px-3 py-2">
          <p className="text-xs font-medium text-amber-200">{t.quantLab.overviewWarnings}</p>
          <ul className="mt-1 space-y-0.5 text-xs text-amber-100/90">
            {overview.major_warnings.slice(0, 5).map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      <GlassPanel variant="compact">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-foreground">{t.quantLab.overviewBrief}</h3>
          <button
            type="button"
            className="rounded border border-zinc-700 px-2 py-1 text-xs text-zinc-300 hover:bg-zinc-900"
            disabled={generateBusy}
            onClick={() => void onGenerateIdeas()}
          >
            {generateBusy ? t.common.loading : t.quantLab.overviewGenerateIdeas}
          </button>
        </div>
        {overview.findings.length === 0 ? (
          <p className="text-sm text-zinc-500">{t.quantLab.overviewNoFindings}</p>
        ) : (
          <ul className="space-y-2">
            {overview.findings.slice(0, 6).map((f) => (
              <li key={f.finding_id} className="rounded border border-zinc-800 px-3 py-2">
                <p className="font-medium text-zinc-100">{f.title}</p>
                <p className="mt-0.5 text-xs leading-relaxed text-zinc-400">{f.explanation}</p>
                <p className="mt-1 text-xs tabular-nums text-zinc-500">{f.supporting_metric}</p>
              </li>
            ))}
          </ul>
        )}
      </GlassPanel>

      <div className="grid gap-4 lg:grid-cols-2">
        <GlassPanel variant="compact">
          <h3 className="mb-2 text-sm font-semibold text-foreground">{t.quantLab.overviewRecommendedIdeas}</h3>
          {overview.recommended_ideas.length === 0 ? (
            <p className="text-sm text-zinc-500">{t.quantLab.overviewNoIdeas}</p>
          ) : (
            <ul className="space-y-2">
              {overview.recommended_ideas.slice(0, 5).map((idea) => (
                <li key={idea.id} className="rounded border border-zinc-800 px-3 py-2 text-xs">
                  <p className="font-medium text-zinc-200">{idea.title}</p>
                  <p className="text-zinc-500">{idea.why_now}</p>
                </li>
              ))}
            </ul>
          )}
        </GlassPanel>

        <GlassPanel variant="compact">
          <h3 className="mb-2 text-sm font-semibold text-foreground">{t.quantLab.overviewRecentActivity}</h3>
          {overview.recent_activity.length === 0 ? (
            <p className="text-sm text-zinc-500">{t.quantLab.overviewNoActivity}</p>
          ) : (
            <ul className="space-y-1 text-xs text-zinc-400">
              {overview.recent_activity.map((a) => (
                <li key={`${a.id}-${a.occurred_at ?? ""}`} className="flex justify-between gap-2">
                  <span className="truncate text-zinc-300">{a.label}</span>
                  <span className="shrink-0 tabular-nums text-zinc-500">{a.occurred_at?.slice(0, 10) ?? "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </GlassPanel>
      </div>

      <details className="analysis-glass-panel analysis-glass-panel--compact p-3">
        <summary className="cursor-pointer text-sm font-medium text-zinc-300">{t.quantLab.overviewMaintenance}</summary>
        <ul className="mt-3 space-y-2">
          {overview.maintenance_actions.map((action) => (
            <li key={action.action_id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div>
                <p className="text-zinc-200">{action.label}</p>
                <p className="text-zinc-500">{action.description}</p>
              </div>
              <button
                type="button"
                disabled={!action.available || actionBusy === action.action_id}
                className="rounded border border-zinc-700 px-2 py-1 text-zinc-300 hover:bg-zinc-900 disabled:opacity-40"
                onClick={() => void onMaintenance(action.action_id)}
              >
                {actionBusy === action.action_id ? t.common.loading : t.quantLab.overviewRunAction}
              </button>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
