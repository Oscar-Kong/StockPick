"use client";

import { useMemo, useState, type ReactNode } from "react";
import clsx from "clsx";
import type {
  AnalyzeDelta,
  AnalyzeFreshness,
  AnalyzeTradePlan,
  V2ScoreResponse,
} from "@/lib/types";
import { useTranslation } from "@/lib/i18n";
import { StatTile } from "@/components/ui/StatTile";
import { SimilarSignalBlock } from "./SimilarSignalBlock";

function fmtNum(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(Number(n))) return "—";
  return Number(n).toFixed(digits);
}

function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(Number(n))) return "—";
  const v = Number(n);
  return `${v > 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

function DecisionBlock({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={clsx("analysis-glass-panel analysis-decision-block", className)}>
      <h3 className="analysis-decision-block__title">{title}</h3>
      <div className="analysis-decision-block__body">{children}</div>
    </section>
  );
}

function FreshnessBadge({
  freshness,
  refreshing,
}: {
  freshness?: AnalyzeFreshness | null;
  refreshing?: boolean;
}) {
  const { t } = useTranslation();
  const status = freshness?.status ?? "unknown";
  const age = freshness?.age_seconds;
  let label = t.analysis.freshnessFresh;
  if (refreshing) label = t.analysis.freshnessRefreshing;
  else if (status === "cached" || status === "stale_timeout") {
    label =
      age != null
        ? t.analysis.freshnessCachedAge.replace("{minutes}", String(Math.max(1, Math.round(age / 60))))
        : t.analysis.freshnessCached;
  } else if (status === "miss") label = t.analysis.freshnessMiss;
  return <span className="text-[11px] text-zinc-500">{label}</span>;
}

function DecisionHeader({
  v2,
  score,
  riskLabel,
  freshness,
  refreshing,
}: {
  v2: V2ScoreResponse | null;
  score: number;
  riskLabel: string;
  freshness?: AnalyzeFreshness | null;
  refreshing?: boolean;
}) {
  const { t } = useTranslation();
  const rec = v2?.recommendation;
  const action = rec?.recommendation ?? t.analysis.decisionPending;
  const confidence = rec?.confidence;
  return (
    <div className="analysis-glass-panel analysis-decision-block analysis-decision-header">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-zinc-500">
            {t.analysis.decisionTitle}
          </p>
          <p className="text-xl font-semibold text-zinc-100">{action}</p>
        </div>
        <FreshnessBadge freshness={freshness} refreshing={refreshing} />
      </div>
      <div className="stat-tile-grid grid grid-cols-2 gap-2 sm:grid-cols-4">
        <StatTile label={t.analysis.scoreChip} value={fmtNum(score, 1)} />
        <StatTile
          label={t.analysis.confidenceLabel}
          value={confidence != null ? `${fmtNum(confidence, 0)}%` : "—"}
        />
        <StatTile label={t.analysis.riskLabel} value={riskLabel} />
        <StatTile
          label={t.analysis.horizonLabel}
          value={rec?.time_horizon_days != null ? `${rec.time_horizon_days}d` : "—"}
        />
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400">
        <span>
          {t.analysis.expectedReturn}: {fmtPct(rec?.expected_return_pct)}
        </span>
        <span>
          {t.analysis.expectedDownside}: {fmtPct(rec?.expected_downside_pct)}
        </span>
      </div>
    </div>
  );
}

function TradePlanCard({ plan }: { plan: AnalyzeTradePlan | null | undefined }) {
  const { t } = useTranslation();
  const uniqueInvalidation = useMemo(() => {
    if (!plan) return [] as string[];
    const raw = [...new Set(plan.invalidation ?? [])].filter(Boolean);
    const bear = (plan.bear_case || "").trim();
    return raw.filter((item) => item.trim() !== bear).slice(0, 3);
  }, [plan]);

  if (!plan) return null;
  const isPenny = (plan.sleeve || "penny") === "penny";

  const metrics: { label: string; value: string }[] = [];
  let holdHint: string | null = null;

  if (isPenny) {
    if (plan.initial_stop != null)
      metrics.push({ label: t.analysis.tradePlanStop, value: `$${fmtNum(plan.initial_stop, 2)}` });
    if (plan.target_1 != null)
      metrics.push({ label: t.analysis.tradePlanTarget1, value: `$${fmtNum(plan.target_1, 2)}` });
    if (plan.target_2 != null)
      metrics.push({ label: t.analysis.tradePlanTarget2, value: `$${fmtNum(plan.target_2, 2)}` });
    if (plan.risk_reward != null)
      metrics.push({ label: t.analysis.tradePlanRR, value: fmtNum(plan.risk_reward, 2) });
    if (plan.max_hold_hint) holdHint = plan.max_hold_hint;
  } else {
    if (plan.fair_value != null)
      metrics.push({ label: t.analysis.tradePlanFairValue, value: `$${fmtNum(plan.fair_value, 2)}` });
    if (plan.time_horizon_days != null)
      metrics.push({ label: t.analysis.horizonLabel, value: `${plan.time_horizon_days}d` });
  }
  if (plan.position_weight_pct != null)
    metrics.push({
      label: t.analysis.tradePlanSize,
      value: `${fmtNum(plan.position_weight_pct, 1)}%`,
    });
  if (plan.stop_loss_pct != null)
    metrics.push({
      label: t.analysis.tradePlanStopPct,
      value: `${fmtNum(plan.stop_loss_pct, 1)}%`,
    });

  const showThesis = Boolean(plan.bull_case || plan.bear_case || uniqueInvalidation.length);

  return (
    <DecisionBlock title={t.analysis.tradePlanTitle}>
      {metrics.length > 0 && (
        <div className="stat-tile-grid grid grid-cols-2 gap-2 sm:grid-cols-3">
          {metrics.map((r) => (
            <StatTile key={r.label} label={r.label} value={r.value} />
          ))}
        </div>
      )}
      {holdHint && (
        <p className="analysis-decision-note">
          <span className="font-medium text-zinc-500">{t.analysis.tradePlanMaxHold}: </span>
          {holdHint}
        </p>
      )}
      {showThesis && (
        <div className="grid gap-2.5 sm:grid-cols-2">
          {plan.bull_case && (
            <div className="analysis-thesis-card analysis-thesis-card--bull">
              <p className="analysis-thesis-card__label">{t.analysis.bullThesis}</p>
              <p className="analysis-thesis-card__body">{plan.bull_case}</p>
            </div>
          )}
          {(plan.bear_case || uniqueInvalidation.length > 0) && (
            <div className="analysis-thesis-card analysis-thesis-card--bear">
              <p className="analysis-thesis-card__label">{t.analysis.invalidationTitle}</p>
              {plan.bear_case && <p className="analysis-thesis-card__body">{plan.bear_case}</p>}
              {uniqueInvalidation.length > 0 && (
                <ul className="analysis-thesis-card__list">
                  {uniqueInvalidation.map((item, idx) => (
                    <li key={`${idx}-${item}`}>{item}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </DecisionBlock>
  );
}

function TopDrivers({ v2 }: { v2: V2ScoreResponse | null }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const factors = useMemo(() => v2?.factors ?? [], [v2?.factors]);
  const sorted = useMemo(
    () => [...factors].sort((a, b) => (b.contribution ?? 0) - (a.contribution ?? 0)),
    [factors]
  );
  const positive = sorted.filter((f) => (f.contribution ?? 0) > 0).slice(0, 3);
  const negative = [...sorted]
    .filter((f) => (f.contribution ?? 0) < 0)
    .sort((a, b) => (a.contribution ?? 0) - (b.contribution ?? 0))
    .slice(0, 3);

  if (!factors.length) return null;

  const bothSides = positive.length > 0 && negative.length > 0;

  return (
    <DecisionBlock title={t.analysis.whyScoreTitle}>
      <div className={bothSides ? "grid gap-3 sm:grid-cols-2" : "grid gap-3"}>
        <div className="analysis-drivers-col">
          <p className="analysis-drivers-col__label analysis-drivers-col__label--pos">
            {t.analysis.positiveDrivers}
          </p>
          <ul className="analysis-drivers-col__list">
            {positive.map((f) => (
              <li key={f.factor_id}>
                <span className="text-emerald-400/90">+</span> {f.display_name || f.factor_id}{" "}
                <span className="tabular-nums text-zinc-500">({fmtNum(f.contribution, 2)})</span>
              </li>
            ))}
            {!positive.length && <li className="text-zinc-500">{t.analysis.driversNone}</li>}
          </ul>
        </div>
        {(negative.length > 0 || bothSides) && (
          <div className="analysis-drivers-col">
            <p className="analysis-drivers-col__label analysis-drivers-col__label--neg">
              {t.analysis.negativeDrivers}
            </p>
            <ul className="analysis-drivers-col__list">
              {negative.map((f) => (
                <li key={f.factor_id}>
                  <span className="text-rose-400/90">−</span> {f.display_name || f.factor_id}{" "}
                  <span className="tabular-nums text-zinc-500">({fmtNum(f.contribution, 2)})</span>
                </li>
              ))}
              {!negative.length && <li className="text-zinc-500">{t.analysis.driversNone}</li>}
            </ul>
          </div>
        )}
      </div>
      <button
        type="button"
        className="cursor-pointer text-[11px] text-zinc-400 underline-offset-2 hover:text-zinc-300 hover:underline"
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? t.analysis.hideFullDrivers : t.analysis.showFullDrivers}
      </button>
      {expanded && (
        <ul className="max-h-44 space-y-1 overflow-y-auto rounded-md border border-zinc-800/70 bg-zinc-950/35 px-2.5 py-2 text-[11px] text-zinc-400">
          {sorted.map((f) => (
            <li key={`all-${f.factor_id}`} className="flex justify-between gap-3">
              <span>{f.display_name || f.factor_id}</span>
              <span className="tabular-nums">{fmtNum(f.contribution, 2)}</span>
            </li>
          ))}
        </ul>
      )}
    </DecisionBlock>
  );
}

function ExecutionQuality({
  plan,
  dataConfidence,
}: {
  plan: AnalyzeTradePlan | null | undefined;
  dataConfidence?: number | null;
}) {
  const { t } = useTranslation();
  if (!plan) return null;
  const items = [
    { label: t.analysis.execRvol, value: plan.relative_volume != null ? `${fmtNum(plan.relative_volume, 1)}x` : null },
    {
      label: t.analysis.execAdv,
      value: plan.avg_dollar_volume != null ? fmtNum(plan.avg_dollar_volume, 0) : null,
    },
    {
      label: t.analysis.execSpread,
      value: plan.spread_estimate != null ? fmtPct(plan.spread_estimate) : null,
    },
    { label: t.analysis.execAtr, value: plan.atr_pct != null ? fmtPct(plan.atr_pct) : null },
    {
      label: t.analysis.execDataConfidence,
      value:
        (dataConfidence ?? plan.data_confidence) != null
          ? `${fmtNum(dataConfidence ?? plan.data_confidence, 0)}%`
          : null,
    },
  ].filter((i) => i.value != null);
  if (!items.length && !plan.liquidity_note) return null;

  return (
    <DecisionBlock title={t.analysis.executionTitle}>
      <dl className="analysis-exec-metrics">
        {items.map((i) => (
          <div key={i.label} className="analysis-exec-metrics__item">
            <dt>{i.label}</dt>
            <dd className="tabular-nums">{i.value}</dd>
          </div>
        ))}
      </dl>
      {plan.liquidity_note && (
        <p className="text-xs leading-relaxed text-amber-200/80">{plan.liquidity_note}</p>
      )}
    </DecisionBlock>
  );
}

function EvidenceStrip({ v2 }: { v2: V2ScoreResponse | null }) {
  const { t } = useTranslation();
  const sim = v2?.similar_signal;
  if (!sim) return null;
  const sample = sim.sample_n ?? 0;
  const minSample = 20;
  return (
    <DecisionBlock title={t.analysis.evidenceStripTitle}>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-zinc-300">
        <span>
          {t.analysis.evidenceSample}: {sample}
        </span>
        {sample >= minSample ? (
          <span>
            {t.analysis.evidenceWinRate}:{" "}
            {sim.win_rate != null ? `${fmtNum((sim.win_rate ?? 0) * 100, 0)}%` : "—"}
          </span>
        ) : (
          <span className="text-amber-200/80">{t.analysis.evidenceSampleTooSmall}</span>
        )}
        <span>
          {t.analysis.evidenceAvgReturn}: {fmtPct(sim.avg_forward_return_pct)}
        </span>
        <span>
          {t.analysis.evidenceMaxDd}: {fmtPct(sim.max_drawdown_pct)}
        </span>
        <span className="text-zinc-500">
          {v2?.strategy_version} · {sim.forward_days ?? 60}d
        </span>
      </div>
      <SimilarSignalBlock data={sim} />
    </DecisionBlock>
  );
}

function ChangeTimeline({ delta }: { delta: AnalyzeDelta | null | undefined }) {
  const { t } = useTranslation();
  if (!delta || !delta.changes?.length) return null;
  return (
    <DecisionBlock title={t.analysis.changeTimelineTitle}>
      <ul className="space-y-1 text-xs text-zinc-300">
        {delta.changes.map((c) => (
          <li key={c.field}>
            <span className="text-zinc-500">{c.field}</span>{" "}
            <span>
              {String(c.from ?? "—")} → {String(c.to ?? "—")}
            </span>
          </li>
        ))}
      </ul>
      {delta.main_change && (
        <p className="text-[11px] text-zinc-500">
          {t.analysis.mainChange}: {delta.main_change}
        </p>
      )}
    </DecisionBlock>
  );
}

export type DecisionOverviewProps = {
  v2: V2ScoreResponse | null;
  score: number;
  riskLabel: string;
  tradePlan?: AnalyzeTradePlan | null;
  delta?: AnalyzeDelta | null;
  freshness?: AnalyzeFreshness | null;
  refreshing?: boolean;
};

/** Decision + trade plan — sits beside position sizing in the Overview grid. */
export function DecisionOverviewLead({
  v2,
  score,
  riskLabel,
  tradePlan,
  freshness,
  refreshing,
}: Omit<DecisionOverviewProps, "delta">) {
  return (
    <div className="analysis-decision-stack">
      <DecisionHeader
        v2={v2}
        score={score}
        riskLabel={riskLabel}
        freshness={freshness}
        refreshing={refreshing}
      />
      <TradePlanCard plan={tradePlan} />
    </div>
  );
}

/** Drivers / execution / evidence / delta — full-width under the Overview grid. */
export function DecisionOverviewDetails({
  v2,
  tradePlan,
  delta,
}: Pick<DecisionOverviewProps, "v2" | "tradePlan" | "delta">) {
  return (
    <div className="analysis-decision-stack">
      <TopDrivers v2={v2} />
      <ExecutionQuality
        plan={tradePlan}
        dataConfidence={v2?.recommendation?.data_confidence?.data_confidence}
      />
      <EvidenceStrip v2={v2} />
      <ChangeTimeline delta={delta} />
    </div>
  );
}

/** Full stack (tests / non-grid callers). */
export function DecisionOverview(props: DecisionOverviewProps) {
  return (
    <div className="analysis-decision-stack">
      <DecisionOverviewLead {...props} />
      <DecisionOverviewDetails
        v2={props.v2}
        tradePlan={props.tradePlan}
        delta={props.delta}
      />
    </div>
  );
}
