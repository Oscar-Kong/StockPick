"""Deterministic research brief — rule-based findings from persisted evidence."""
from __future__ import annotations

import hashlib
from typing import Any

from buckets import DEFAULT_BUCKET
from models.schemas_research import ExperimentType, ResearchBriefFinding

IC_DRIFT_THRESHOLD = 0.03
HORIZON_IC_GAP = 0.04
MIN_PROMOTE_SAMPLE = 100
LOW_RESOLUTION_PCT = 0.4
HIGH_TURNOVER = 0.35
LONG_HALF_LIFE_SESSIONS = 120
IC_STALE_DAYS = 7


def _finding_id(seed: str) -> str:
    return f"finding_{hashlib.sha256(seed.encode()).hexdigest()[:12]}"


def build_research_brief(
    *,
    sleeve: str,
    factor_ic_rows: list[dict[str, Any]],
    factor_ic_history: list[dict[str, Any]],
    walk_forward: dict[str, Any] | None,
    pairs_summary: dict[str, Any] | None,
    predictions_resolved: int,
    predictions_unresolved: int,
    feedback_by_rec: dict[str, dict[str, Any]],
    data_freshness: str,
    factor_ic_stale: bool,
    walk_forward_stale: bool,
    jobs_failed: int,
) -> list[ResearchBriefFinding]:
    findings: list[ResearchBriefFinding] = []

    # --- Factor IC drift vs history ---
    if factor_ic_rows and factor_ic_history:
        current_by_factor: dict[str, float] = {}
        for row in factor_ic_rows:
            fid = str(row.get("factor_id") or "")
            ic = row.get("ic")
            if fid and ic is not None:
                current_by_factor[fid] = float(ic)

        hist_by_factor: dict[str, list[float]] = {}
        for row in factor_ic_history:
            fid = str(row.get("factor_id") or "")
            ic = row.get("ic")
            if fid and ic is not None:
                hist_by_factor.setdefault(fid, []).append(float(ic))

        for fid, current_ic in current_by_factor.items():
            hist = hist_by_factor.get(fid) or []
            if len(hist) < 3:
                continue
            long_term = sum(hist) / len(hist)
            delta = current_ic - long_term
            if abs(delta) >= IC_DRIFT_THRESHOLD:
                direction = "improved" if delta > 0 else "deteriorated"
                findings.append(
                    ResearchBriefFinding(
                        finding_id=_finding_id(f"ic_drift:{sleeve}:{fid}"),
                        title=f"Factor {fid} IC {direction} vs long-term average",
                        explanation=(
                            f"Latest IC {current_ic:.3f} differs from historical mean "
                            f"{long_term:.3f} by {delta:+.3f}."
                        ),
                        supporting_metric=f"delta_ic={delta:+.3f}",
                        source_reference=f"factor_ic_history:{sleeve}:{fid}",
                        why_it_matters="Sustained IC drift may require weight review or factor retirement.",
                        confidence=min(0.95, 0.5 + abs(delta)),
                        evidence_impact="informational",
                        suggested_experiment_type="factor_validation",
                        suggested_parameters={"factor_id": fid, "sleeve": sleeve},
                    )
                )

    # --- Horizon IC gap ---
    by_factor_horizon: dict[str, dict[int, float]] = {}
    for row in factor_ic_rows:
        fid = str(row.get("factor_id") or "")
        h = row.get("horizon_days")
        ic = row.get("ic")
        if fid and h is not None and ic is not None:
            by_factor_horizon.setdefault(fid, {})[int(h)] = float(ic)

    for fid, horizons in by_factor_horizon.items():
        if len(horizons) < 2:
            continue
        vals = list(horizons.values())
        gap = max(vals) - min(vals)
        if gap >= HORIZON_IC_GAP:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"horizon_gap:{sleeve}:{fid}"),
                    title=f"Factor {fid} performance differs across horizons",
                    explanation=f"IC spread across horizons is {gap:.3f} ({horizons}).",
                    supporting_metric=f"horizon_ic_spread={gap:.3f}",
                    source_reference=f"factor_ic_history:{sleeve}:{fid}",
                    why_it_matters="Horizon instability suggests the signal may be noise at some holding periods.",
                    confidence=0.65,
                    evidence_impact="informational",
                    suggested_experiment_type="factor_validation",
                    suggested_parameters={"factor_id": fid, "sleeve": sleeve, "horizons": list(horizons.keys())},
                )
            )

    # --- Promoted factor insufficient sample ---
    for row in factor_ic_rows:
        fid = str(row.get("factor_id") or "")
        ic = row.get("ic")
        n = int(row.get("sample_n") or 0)
        if not fid or ic is None:
            continue
        if float(ic) >= 0.05 and n < MIN_PROMOTE_SAMPLE:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"promote_sample:{sleeve}:{fid}"),
                    title=f"Strong IC factor {fid} has limited sample size",
                    explanation=f"IC {float(ic):.3f} with only n={n} — below promote threshold n≥{MIN_PROMOTE_SAMPLE}.",
                    supporting_metric=f"sample_n={n}",
                    source_reference=f"factor_ic_history:{sleeve}:{fid}",
                    why_it_matters="Promotion decisions need adequate cross-sectional depth.",
                    confidence=0.7,
                    evidence_impact="informational",
                    suggested_experiment_type="factor_validation",
                    suggested_parameters={"factor_id": fid, "sleeve": sleeve},
                )
            )

    # --- Prediction resolution coverage ---
    total_pred = predictions_resolved + predictions_unresolved
    if total_pred > 0:
        unresolved_pct = predictions_unresolved / total_pred
        if unresolved_pct >= LOW_RESOLUTION_PCT:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"pred_coverage:{sleeve}"),
                    title="Prediction outcome resolution coverage is low",
                    explanation=(
                        f"{predictions_unresolved} of {total_pred} recent predictions unresolved "
                        f"({unresolved_pct:.0%})."
                    ),
                    supporting_metric=f"unresolved_pct={unresolved_pct:.2f}",
                    source_reference="prediction_snapshots",
                    why_it_matters="Calibration checks need resolved forward outcomes.",
                    confidence=0.75,
                    evidence_impact="informational",
                    suggested_experiment_type="prediction_calibration",
                    suggested_parameters={"sleeve": sleeve},
                )
            )

    # --- Recommendation category underperformance ---
    for rec, stats in feedback_by_rec.items():
        err = stats.get("mean_error_pct")
        count = int(stats.get("count") or 0)
        if err is None or count < 5:
            continue
        if float(err) > 15.0:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"rec_cal:{rec}"),
                    title=f"Recommendation category '{rec}' shows high forecast error",
                    explanation=f"Mean forecast error {float(err):.1f}% across {count} resolved outcomes.",
                    supporting_metric=f"mean_error_pct={float(err):.1f}",
                    source_reference=f"prediction_outcomes:{rec}",
                    why_it_matters="Category-level drift may indicate miscalibrated conviction tiers.",
                    confidence=0.6,
                    evidence_impact="contradicting",
                    suggested_experiment_type="prediction_calibration",
                    suggested_parameters={"recommendation": rec},
                )
            )

    # --- Walk-forward instability ---
    if walk_forward:
        periods = int(walk_forward.get("periods_scored") or 0)
        agg = walk_forward.get("aggregate_horizons") or {}
        ics: list[float] = []
        for stats in agg.values():
            if isinstance(stats, dict) and stats.get("mean_rank_ic") is not None:
                ics.append(float(stats["mean_rank_ic"]))
        if periods > 0 and periods < 5:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"wf_unstable:{sleeve}"),
                    title="Walk-forward evidence covers too few periods",
                    explanation=f"Only {periods} scored periods in latest walk-forward run.",
                    supporting_metric=f"periods_scored={periods}",
                    source_reference=f"backtest_runs:{walk_forward.get('run_id', '')}",
                    why_it_matters="Walk-forward with few windows is prone to overfitting.",
                    confidence=0.8,
                    evidence_impact="informational",
                    suggested_experiment_type="walk_forward",
                    suggested_parameters={"sleeve": sleeve, "preset": "robust"},
                )
            )
        if ics and len(ics) >= 2:
            same_sign = all(x >= 0 for x in ics) or all(x <= 0 for x in ics)
            if not same_sign:
                findings.append(
                    ResearchBriefFinding(
                        finding_id=_finding_id(f"wf_horizon_sign:{sleeve}"),
                        title="Walk-forward rank IC sign flips across horizons",
                        explanation=f"Horizon IC values: {ics}",
                        supporting_metric="directional_inconsistency",
                        source_reference=f"backtest_runs:{walk_forward.get('run_id', '')}",
                        why_it_matters="Inconsistent horizon signs weaken confidence in the edge.",
                        confidence=0.7,
                        evidence_impact="contradicting",
                        suggested_experiment_type="walk_forward",
                        suggested_parameters={"sleeve": sleeve},
                    )
                )
        turnover = walk_forward.get("mean_turnover")
        if turnover is not None and float(turnover) > HIGH_TURNOVER:
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id(f"wf_turnover:{sleeve}"),
                    title="Walk-forward turnover is high relative to gross spread",
                    explanation=f"Mean turnover {float(turnover):.2f} exceeds {HIGH_TURNOVER:.0%} threshold.",
                    supporting_metric=f"mean_turnover={float(turnover):.3f}",
                    source_reference=f"backtest_runs:{walk_forward.get('run_id', '')}",
                    why_it_matters="High turnover erodes net returns after costs.",
                    confidence=0.75,
                    evidence_impact="informational",
                    suggested_experiment_type="walk_forward",
                    suggested_parameters={"sleeve": sleeve},
                )
            )

    # --- Pairs impractical half-life ---
    if pairs_summary:
        pairs = pairs_summary.get("pairs") or []
        if isinstance(pairs, list):
            for p in pairs[:5]:
                if not isinstance(p, dict):
                    continue
                hl = p.get("half_life_sessions")
                if hl is not None and float(hl) > LONG_HALF_LIFE_SESSIONS:
                    pair = p.get("pair") or []
                    label = "/".join(pair) if pair else "pair"
                    findings.append(
                        ResearchBriefFinding(
                            finding_id=_finding_id(f"pair_hl:{label}"),
                            title=f"Pair {label} has impractical mean-reversion half-life",
                            explanation=f"Half-life {float(hl):.0f} sessions exceeds practical threshold.",
                            supporting_metric=f"half_life_sessions={float(hl):.0f}",
                            source_reference=f"pairs_research_runs:{pairs_summary.get('run_id', '')}",
                            why_it_matters="Slow mean reversion makes pairs capital-inefficient.",
                            confidence=0.65,
                            evidence_impact="informational",
                            suggested_experiment_type="pairs_discovery",
                            suggested_parameters={"pair": pair},
                        )
                    )
        excluded = pairs_summary.get("excluded") or []
        used = pairs_summary.get("symbols_used") or []
        if excluded and len(excluded) > len(used):
            findings.append(
                ResearchBriefFinding(
                    finding_id=_finding_id("pairs_excluded"),
                    title="Too many symbols excluded from pairs universe",
                    explanation=f"{len(excluded)} excluded vs {len(used)} used in last pairs run.",
                    supporting_metric=f"excluded={len(excluded)}",
                    source_reference=f"pairs_research_runs:{pairs_summary.get('run_id', '')}",
                    why_it_matters="Sparse universes reduce pair discovery reliability.",
                    confidence=0.6,
                    evidence_impact="integrity_blocker" if len(used) < 3 else "informational",
                    suggested_experiment_type="pairs_discovery",
                    suggested_parameters={},
                )
            )

    # --- Data freshness blocks analysis ---
    if factor_ic_stale or data_freshness in ("stale", "degraded", "critical"):
        findings.append(
            ResearchBriefFinding(
                finding_id=_finding_id(f"data_fresh:{sleeve}"),
                title="Data freshness may block reliable analysis",
                explanation=f"Overall data freshness: {data_freshness}. IC stale: {factor_ic_stale}.",
                supporting_metric=f"freshness={data_freshness}",
                source_reference="quant_health",
                why_it_matters="Stale inputs invalidate factor and outcome conclusions.",
                confidence=0.85,
                evidence_impact="integrity_blocker",
                suggested_experiment_type="factor_validation",
                suggested_parameters={"action": "refresh_data"},
            )
        )

    if walk_forward_stale:
        findings.append(
            ResearchBriefFinding(
                finding_id=_finding_id(f"wf_stale:{sleeve}"),
                title="Walk-forward evidence is stale",
                explanation="Latest walk-forward run exceeds freshness threshold.",
                supporting_metric="walk_forward_stale=true",
                source_reference="backtest_runs",
                why_it_matters="Outdated validation may not reflect current factor weights.",
                confidence=0.7,
                evidence_impact="informational",
                suggested_experiment_type="walk_forward",
                suggested_parameters={"sleeve": sleeve},
            )
        )

    if jobs_failed > 0:
        findings.append(
            ResearchBriefFinding(
                finding_id=_finding_id("jobs_failed"),
                title="Recent quant jobs failed or need attention",
                explanation=f"{jobs_failed} failed/blocked jobs in the attention window.",
                supporting_metric=f"failed_jobs={jobs_failed}",
                source_reference="job_logs",
                why_it_matters="Failed maintenance jobs leave evidence incomplete.",
                confidence=0.9,
                evidence_impact="integrity_blocker",
                suggested_experiment_type="factor_validation",
                suggested_parameters={"action": "retry_jobs"},
            )
        )

    return findings
