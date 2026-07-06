"use client";

import { useCallback, useEffect, useState } from "react";
import clsx from "clsx";
import { getDailyTradingPlanReview, saveDailyTradingPlanReview } from "@/lib/api/portfolio";
import { useTranslation } from "@/lib/i18n";
import type {
  DailyDashboardResponse,
  DailyTradingPlanDecision,
  DailyTradingPlanRuleCheck,
} from "@/lib/types";
import { SectionCard } from "@/components/ui/AppCard";
import { SecondaryButton } from "@/components/ui/buttons";
import { SummaryStrip, SummaryStripItem } from "@/components/ui/SummaryStrip";

function decisionTone(
  decision: DailyTradingPlanDecision,
): "positive" | "negative" | "warning" | "muted" | "default" {
  if (decision === "buy") return "positive";
  if (decision === "exit") return "negative";
  if (decision === "reduce" || decision === "watch") return "warning";
  if (decision === "stay_in_cash") return "muted";
  return "default";
}

function decisionLabel(
  decision: DailyTradingPlanDecision,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  const labels: Record<DailyTradingPlanDecision, string> = {
    buy: t.home.dailyTradingPlanDecisionBuy,
    manage: t.home.dailyTradingPlanDecisionManage,
    reduce: t.home.dailyTradingPlanDecisionReduce,
    exit: t.home.dailyTradingPlanDecisionExit,
    watch: t.home.dailyTradingPlanDecisionWatch,
    stay_in_cash: t.home.dailyTradingPlanDecisionStayInCash,
  };
  return labels[decision] ?? decision;
}

function focusStatusLabel(
  status: string,
  t: ReturnType<typeof useTranslation>["t"],
): string {
  if (status === "qualified") return t.home.dailyTradingPlanStatusQualified;
  if (status === "rejected") return t.home.dailyTradingPlanStatusRejected;
  return t.home.dailyTradingPlanStatusPending;
}

function ruleStatusLabel(
  status: DailyTradingPlanRuleCheck["status"],
  t: ReturnType<typeof useTranslation>["t"],
): string {
  if (status === "pass") return t.home.dailyTradingPlanRulePass;
  if (status === "fail") return t.home.dailyTradingPlanRuleFail;
  return t.home.dailyTradingPlanRuleUnavailable;
}

function ExposureBar({
  current,
  max,
  available,
  label,
}: {
  current: number;
  max: number;
  available: number;
  label: string;
}) {
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0;
  const tone =
    pct >= 100
      ? "daily-trading-plan__exposure-fill--high"
      : pct >= 75
        ? "daily-trading-plan__exposure-fill--mid"
        : "daily-trading-plan__exposure-fill--low";

  return (
    <div className="daily-trading-plan__exposure" aria-label={label}>
      <div className="daily-trading-plan__exposure-track" role="presentation">
        <div className={clsx("daily-trading-plan__exposure-fill", tone)} style={{ width: `${pct}%` }} />
      </div>
      <p className="daily-trading-plan__exposure-caption finance-value">
        {current.toFixed(1)}% used · {available.toFixed(1)}% room · {max.toFixed(0)}% cap
      </p>
    </div>
  );
}

export interface DailyTradingPlanCardProps {
  data: DailyDashboardResponse;
  loading?: boolean;
  error?: string | null;
}

export function DailyTradingPlanCard({ data, loading, error }: DailyTradingPlanCardProps) {
  const { t } = useTranslation();
  const plan = data.daily_trading_plan;
  const [reviewNotes, setReviewNotes] = useState("");
  const [planFollowed, setPlanFollowed] = useState<boolean | null>(null);
  const [actualAction, setActualAction] = useState("");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  const tradingDate = plan?.as_of?.slice(0, 10) ?? new Date().toISOString().slice(0, 10);

  useEffect(() => {
    if (!plan) return;
    let cancelled = false;
    getDailyTradingPlanReview(tradingDate)
      .then((row) => {
        if (cancelled || !row) return;
        setReviewNotes(row.user_notes ?? "");
        setPlanFollowed(row.plan_followed ?? null);
        setActualAction(row.actual_action ?? "");
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [plan?.plan_id, tradingDate, plan]);

  const onSaveReview = useCallback(async () => {
    if (!plan) return;
    setSaveState("saving");
    try {
      await saveDailyTradingPlanReview({
        trading_date: tradingDate,
        plan_id: plan.plan_id,
        planned_decision: plan.decision,
        primary_candidate: plan.primary_candidate?.symbol ?? null,
        plan_followed: planFollowed,
        actual_action: actualAction || null,
        user_notes: reviewNotes,
      });
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }, [plan, tradingDate, planFollowed, actualAction, reviewNotes]);

  if (loading) {
    return (
      <SectionCard title={t.home.dailyTradingPlanTitle} variant="elevated" className="daily-trading-plan">
        <p className="text-sm text-secondary">{t.home.dailyTradingPlanLoading}</p>
      </SectionCard>
    );
  }

  if (error) {
    return (
      <SectionCard title={t.home.dailyTradingPlanTitle} variant="muted" className="daily-trading-plan">
        <p className="text-sm text-sell">{error}</p>
      </SectionCard>
    );
  }

  if (!plan) {
    return (
      <SectionCard title={t.home.dailyTradingPlanTitle} variant="muted" className="daily-trading-plan">
        <p className="text-sm text-secondary">{t.home.dailyTradingPlanEmpty}</p>
      </SectionCard>
    );
  }

  const stale = Boolean(data.decision_stale_warning || data.freshness?.overall_status === "stale");
  const candidate = plan.primary_candidate;
  const failedRules = plan.rule_checklist.filter((rule) => rule.status === "fail");
  const sessionLabel = plan.market_session.replace(/_/g, " ");

  return (
    <SectionCard
      title={t.home.dailyTradingPlanTitle}
      subtitle={t.home.dailyTradingPlanSubtitle}
      variant="elevated"
      className="daily-trading-plan"
    >
      <div className="daily-trading-plan__body">
        {stale && (
          <p className="daily-trading-plan__alert daily-trading-plan__alert--warn" role="status">
            {data.decision_stale_warning ?? t.home.dailyTradingPlanStale}
          </p>
        )}

        <SummaryStrip className="daily-trading-plan__metrics">
          <SummaryStripItem
            label={t.home.dailyTradingPlanDecision}
            value={decisionLabel(plan.decision, t)}
            tone={decisionTone(plan.decision)}
          />
          <SummaryStripItem
            label={t.home.dailyTradingPlanConfidence}
            value={`${plan.confidence.toFixed(0)}%`}
          />
          <SummaryStripItem
            label={t.home.dailyTradingPlanExposure}
            value={`${plan.current_short_term_exposure_pct.toFixed(1)}%`}
            hint={`${plan.available_risk_capacity_pct.toFixed(1)}% ${t.home.dailyTradingPlanExposureRoom}`}
          />
          <SummaryStripItem
            label={t.home.dailyTradingPlanPositions}
            value={String(plan.active_short_term_positions)}
            hint={sessionLabel}
            tone="muted"
          />
        </SummaryStrip>

        <ExposureBar
          current={plan.current_short_term_exposure_pct}
          max={plan.maximum_short_term_exposure_pct}
          available={plan.available_risk_capacity_pct}
          label={t.home.dailyTradingPlanExposure}
        />

        <p className="daily-trading-plan__summary">{plan.summary}</p>

        {plan.cash_reason && (
          <p className="daily-trading-plan__alert daily-trading-plan__alert--info">{plan.cash_reason}</p>
        )}

        {plan.holiday_risk.recommend_reduce_exposure && plan.holiday_risk.reason && (
          <p className="daily-trading-plan__alert daily-trading-plan__alert--warn">{plan.holiday_risk.reason}</p>
        )}

        {plan.focus_list.length > 0 && (
          <section className="daily-trading-plan__section" aria-labelledby="daily-plan-focus-heading">
            <h3 id="daily-plan-focus-heading" className="daily-trading-plan__section-title">
              {t.home.dailyTradingPlanFocus}
            </h3>
            <div className="dense-table-wrap">
              <table className="dense-table daily-trading-plan__focus-table">
                <thead>
                  <tr>
                    <th scope="col" className="col-num">
                      {t.home.dailyTradingPlanFocusRank}
                    </th>
                    <th scope="col">{t.home.dailyTradingPlanFocusSymbol}</th>
                    <th scope="col">{t.home.dailyTradingPlanFocusStatus}</th>
                    <th scope="col">{t.home.dailyTradingPlanFocusNote}</th>
                  </tr>
                </thead>
                <tbody>
                  {plan.focus_list.map((item) => (
                    <tr key={item.symbol}>
                      <td className="col-num finance-value">#{item.rank}</td>
                      <td className="text-symbol font-medium">{item.symbol}</td>
                      <td>
                        <span
                          className={clsx(
                            "daily-trading-plan__status",
                            item.status === "qualified" && "daily-trading-plan__status--pass",
                            item.status === "rejected" && "daily-trading-plan__status--fail",
                            item.status !== "qualified" &&
                              item.status !== "rejected" &&
                              "daily-trading-plan__status--pending",
                          )}
                        >
                          {focusStatusLabel(item.status, t)}
                        </span>
                      </td>
                      <td className="text-secondary">
                        {(item.reasons[0] ?? item.rejection_reasons[0]) || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {plan.rule_checklist.length > 0 && (
          <section className="daily-trading-plan__section" aria-labelledby="daily-plan-rules-heading">
            <h3 id="daily-plan-rules-heading" className="daily-trading-plan__section-title">
              {t.home.dailyTradingPlanRules}
              {failedRules.length > 0 && (
                <span className="daily-trading-plan__rules-fail-count">
                  {failedRules.length} {t.home.dailyTradingPlanRulesFailed}
                </span>
              )}
            </h3>
            <ul className="daily-trading-plan__rules">
              {plan.rule_checklist.map((rule) => (
                <li
                  key={rule.rule_id}
                  className={clsx(
                    "daily-trading-plan__rule",
                    rule.status === "pass" && "daily-trading-plan__rule--pass",
                    rule.status === "fail" && "daily-trading-plan__rule--fail",
                    rule.status !== "pass" && rule.status !== "fail" && "daily-trading-plan__rule--pending",
                  )}
                >
                  <span className="daily-trading-plan__rule-status">{ruleStatusLabel(rule.status, t)}</span>
                  <span className="daily-trading-plan__rule-label">
                    {rule.label}
                    {rule.evidence ? ` — ${rule.evidence}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {candidate && (
          <details className="daily-trading-plan__details">
            <summary className="daily-trading-plan__details-summary">
              {t.home.dailyTradingPlanTradeSetup} — {candidate.symbol}
            </summary>
            <dl className="daily-trading-plan__setup-grid">
              <div>
                <dt>{t.home.dailyTradingPlanEntry}</dt>
                <dd>{candidate.entry_condition}</dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanEarliest}</dt>
                <dd>{candidate.entry_not_before}</dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanMaxPosition}</dt>
                <dd className="finance-value">${candidate.maximum_position_value.toLocaleString()}</dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanStop}</dt>
                <dd className="finance-value">
                  ${candidate.stop_price.toFixed(2)} ({candidate.stop_loss_pct}%)
                </dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanFirstTarget}</dt>
                <dd className="finance-value">
                  ${candidate.first_target_price.toFixed(2)} (+{candidate.first_target_gain_pct}%)
                </dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanPartialSale}</dt>
                <dd>
                  {t.home.dailyTradingPlanPartialSaleValue.replace(
                    "{pct}",
                    String(candidate.first_target_sell_fraction_pct),
                  )}
                </dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanRiskReward}</dt>
                <dd className="finance-value">{candidate.risk_reward_ratio.toFixed(2)}</dd>
              </div>
              <div>
                <dt>{t.home.dailyTradingPlanDataConfidence}</dt>
                <dd className="finance-value">{candidate.data_confidence.toFixed(0)}</dd>
              </div>
            </dl>
          </details>
        )}

        {candidate && candidate.supporting_evidence.length > 0 && (
          <details className="daily-trading-plan__details">
            <summary className="daily-trading-plan__details-summary">{t.home.dailyTradingPlanWhy}</summary>
            <ul className="daily-trading-plan__evidence">
              {candidate.supporting_evidence.map((item) => (
                <li key={item}>{item}</li>
              ))}
              <li>
                {t.home.dailyTradingPlanVolume}: {candidate.volume_classification}
              </li>
              <li>
                {t.home.dailyTradingPlanNews}: {candidate.news_classification}
              </li>
              <li>
                {t.home.dailyTradingPlanTrend}: {candidate.trend_state}
              </li>
              {plan.data_freshness?.as_of != null && (
                <li>
                  {t.home.dailyTradingPlanAsOf} {String(plan.data_freshness.as_of)}
                </li>
              )}
            </ul>
          </details>
        )}

        <details className="daily-trading-plan__details">
          <summary className="daily-trading-plan__details-summary">{t.home.dailyTradingPlanReview}</summary>
          <div className="daily-trading-plan__review">
            <fieldset className="daily-trading-plan__review-followed">
              <legend className="sr-only">{t.home.dailyTradingPlanReview}</legend>
              <label className="daily-trading-plan__review-option">
                <input
                  type="radio"
                  name="plan-followed"
                  checked={planFollowed === true}
                  onChange={() => setPlanFollowed(true)}
                />
                {t.home.dailyTradingPlanFollowed}
              </label>
              <label className="daily-trading-plan__review-option">
                <input
                  type="radio"
                  name="plan-followed"
                  checked={planFollowed === false}
                  onChange={() => setPlanFollowed(false)}
                />
                {t.home.dailyTradingPlanDeviated}
              </label>
            </fieldset>
            <label className="daily-trading-plan__review-field">
              <span className="daily-trading-plan__review-label">{t.home.dailyTradingPlanActualAction}</span>
              <input
                className="input-field"
                placeholder={t.home.dailyTradingPlanActualActionPlaceholder}
                value={actualAction}
                onChange={(e) => setActualAction(e.target.value)}
              />
            </label>
            <label className="daily-trading-plan__review-field">
              <span className="daily-trading-plan__review-label">{t.home.dailyTradingPlanNotes}</span>
              <textarea
                className="input-field daily-trading-plan__review-textarea"
                rows={2}
                placeholder={t.home.dailyTradingPlanNotesPlaceholder}
                value={reviewNotes}
                onChange={(e) => setReviewNotes(e.target.value)}
              />
            </label>
            <div className="daily-trading-plan__review-actions">
              <SecondaryButton onClick={() => void onSaveReview()} disabled={saveState === "saving"}>
                {saveState === "saving" ? t.home.dailyTradingPlanSaving : t.home.dailyTradingPlanSaveReview}
              </SecondaryButton>
              {saveState === "saved" && (
                <span className="text-xs text-buy" role="status">
                  {t.home.dailyTradingPlanSaved}
                </span>
              )}
              {saveState === "error" && (
                <span className="text-xs text-sell" role="alert">
                  {t.home.dailyTradingPlanSaveFailed}
                </span>
              )}
            </div>
          </div>
        </details>

        <p className="daily-trading-plan__disclaimer">{plan.disclaimer}</p>
      </div>
    </SectionCard>
  );
}
