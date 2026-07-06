"""Cohesive Quant Lab research overview — bounded reads, no heavy jobs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from buckets import DEFAULT_BUCKET
from config import DEMO_MODE, SCORE_ENGINE_V2_ENABLED, TRADE_FEEDBACK_ENABLED
from data.db_engine import get_engine
from engines.quant_models import FactorIcHistory, PredictionSnapshot, ResearchExperiment
from models.schemas_research import (
    EvidenceMaintenanceAction,
    ResearchActivityItem,
    ResearchOverviewResponse,
)
from services.quant_lab_summary_service import build_jobs_last_run, get_quant_lab_evidence
from services.research_brief_service import build_research_brief
from services.research_experiments_service import get_experiment
from services.research_ideas_service import list_ideas
from services.research_run_service import list_runs
from sqlalchemy import func
from sqlalchemy.orm import Session


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def _confidence_from_evidence(evidence) -> tuple[str, int]:
    cards = [
        evidence.factor_ic,
        evidence.walk_forward,
        evidence.predictions,
        evidence.pairs,
        evidence.jobs,
    ]
    score = 100
    status = "reliable"
    stale_count = sum(1 for c in cards if c.stale)
    unavailable = sum(1 for c in cards if not c.available)
    attention = sum(1 for c in cards if c.trust_indicator in ("needs_attention", "insufficient_sample"))

    if unavailable >= 3:
        status = "insufficient_data"
        score = 25
    elif attention > 0 or stale_count >= 2:
        status = "usable_with_warnings"
        score = max(40, 100 - stale_count * 15 - attention * 10 - unavailable * 8)
    elif stale_count == 1 or unavailable == 1:
        status = "usable_with_warnings"
        score = 70
    else:
        score = max(55, 100 - unavailable * 5)

    return status, min(100, max(0, score))


def _data_freshness_label(evidence) -> str:
    if evidence.factor_ic.stale or evidence.walk_forward.stale:
        return "stale"
    if not evidence.factor_ic.available:
        return "degraded"
    if evidence.jobs.trust_indicator == "needs_attention":
        return "degraded"
    return "fresh"


def _load_ic_rows(sleeve: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    engine = get_engine()
    with Session(engine) as session:
        latest = (
            session.query(FactorIcHistory.as_of_date)
            .filter(FactorIcHistory.sleeve == sleeve)
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(1)
            .scalar()
        )
        if not latest:
            return [], [], None
        current = (
            session.query(FactorIcHistory)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date == latest)
            .all()
        )
        history = (
            session.query(FactorIcHistory)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date != latest)
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(200)
            .all()
        )

    def row_dict(r: FactorIcHistory) -> dict[str, Any]:
        return {
            "factor_id": r.factor_id,
            "horizon_days": r.horizon_days,
            "ic": r.ic,
            "sample_n": r.sample_n,
            "as_of_date": r.as_of_date,
        }

    return [row_dict(r) for r in current], [row_dict(r) for r in history], str(latest)


def _prediction_counts() -> tuple[int, int]:
    if not SCORE_ENGINE_V2_ENABLED:
        return 0, 0
    engine = get_engine()
    with Session(engine) as session:
        from engines.quant_models import PredictionOutcome

        total = session.query(func.count(PredictionSnapshot.id)).scalar() or 0
        resolved = session.query(func.count(PredictionOutcome.prediction_id)).scalar() or 0
    unresolved = max(0, int(total) - int(resolved))
    return int(resolved), unresolved


def _feedback_by_recommendation() -> dict[str, dict[str, Any]]:
    if not TRADE_FEEDBACK_ENABLED:
        return {}
    try:
        from engines.prediction.snapshots import list_recent_snapshots

        snaps = list_recent_snapshots(limit=100)
        buckets: dict[str, list[float]] = {}
        for s in snaps:
            rec = str(s.get("recommendation") or "unknown")
            outcome = s.get("outcome")
            if not outcome or not isinstance(outcome, dict):
                continue
            err = s.get("forecast_error_pct")
            if err is None:
                continue
            buckets.setdefault(rec, []).append(float(err))
        return {
            rec: {"mean_error_pct": sum(v) / len(v), "count": len(v)}
            for rec, v in buckets.items()
            if v
        }
    except Exception:
        return {}


def _latest_experiment() -> Any:
    engine = get_engine()
    with Session(engine) as session:
        row = session.query(ResearchExperiment).order_by(ResearchExperiment.updated_at.desc()).limit(1).first()
        if not row:
            return None
        return get_experiment(row.id)


def _recent_activity(sleeve: str, limit: int = 8) -> list[ResearchActivityItem]:
    items: list[ResearchActivityItem] = []
    runs = list_runs(sleeve=sleeve, limit=limit, backfill=False)
    for r in runs.runs:
        items.append(
            ResearchActivityItem(
                id=r.run_id,
                activity_type=r.run_type,
                label=r.name,
                occurred_at=r.completed_at.isoformat() if r.completed_at else None,
                status=r.status,
                run_id=r.run_id,
            )
        )
    evidence = get_quant_lab_evidence(sleeve)
    if evidence.jobs.available and evidence.jobs.generated_at:
        items.append(
            ResearchActivityItem(
                id="jobs",
                activity_type="quant_job",
                label=str(evidence.jobs.main_metric.value if evidence.jobs.main_metric else "quant job"),
                occurred_at=evidence.jobs.generated_at,
                status=evidence.jobs.status,
            )
        )
    return items[:limit]


def _maintenance_actions() -> list[EvidenceMaintenanceAction]:
    actions: list[EvidenceMaintenanceAction] = [
        EvidenceMaintenanceAction(
            action_id="ic_panel",
            label="Run IC panel update",
            description="Recompute factor IC history for all sleeves",
            endpoint="/api/v2/jobs/ic-panel",
            available=SCORE_ENGINE_V2_ENABLED and not DEMO_MODE,
            reason_unavailable="Disabled in demo or v2 off" if DEMO_MODE or not SCORE_ENGINE_V2_ENABLED else None,
        ),
        EvidenceMaintenanceAction(
            action_id="forward_labels",
            label="Build forward labels",
            description="Materialize forward return labels for research",
            endpoint="/api/v2/jobs/forward-labels",
            available=SCORE_ENGINE_V2_ENABLED and not DEMO_MODE,
            reason_unavailable="Disabled in demo or v2 off" if DEMO_MODE or not SCORE_ENGINE_V2_ENABLED else None,
        ),
        EvidenceMaintenanceAction(
            action_id="resolve_outcomes",
            label="Resolve eligible outcomes",
            description="Resolve prediction snapshots with matured horizons",
            endpoint="/api/v2/jobs/resolve-outcomes",
            available=SCORE_ENGINE_V2_ENABLED and TRADE_FEEDBACK_ENABLED and not DEMO_MODE,
            reason_unavailable="Feedback disabled or demo mode"
            if not TRADE_FEEDBACK_ENABLED or DEMO_MODE
            else None,
        ),
        EvidenceMaintenanceAction(
            action_id="quant_daily_jobs",
            label="Retry quant daily jobs",
            description="Enqueue regime, IC panel, and outcome resolution",
            endpoint="/api/v2/jobs/enqueue/quant_daily_jobs",
            available=not DEMO_MODE,
            reason_unavailable="Disabled in demo mode" if DEMO_MODE else None,
        ),
        EvidenceMaintenanceAction(
            action_id="refresh_evidence",
            label="Refresh evidence index",
            description="Backfill unified research run index from persisted stores",
            endpoint="/api/v2/research/runs/backfill?limit=100",
            available=True,
        ),
    ]
    return actions


def get_research_overview(sleeve: str = DEFAULT_BUCKET) -> ResearchOverviewResponse:
    from core.sleeve import normalize_sleeve

    sleeve = normalize_sleeve(sleeve)
    from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
    from services.version_pin import pinned_versions

    evidence = get_quant_lab_evidence(sleeve)
    conf_status, conf_score = _confidence_from_evidence(evidence)
    freshness = _data_freshness_label(evidence)

    versions = pinned_versions()
    strategy_v = versions.get("strategy_version") or STRATEGY_VERSION
    factor_v = versions.get("factor_model_version") or FACTOR_MODEL_VERSION

    regime: str | None = None
    try:
        if SCORE_ENGINE_V2_ENABLED:
            from engines.weighting.weight_store import WeightStore

            regime = WeightStore.current_regime()
    except Exception:
        regime = None

    ic_rows, ic_hist, _ = _load_ic_rows(sleeve)
    wf_raw = None
    try:
        from services.quant_lab_summary_service import load_latest_walk_forward_run

        wf_raw = load_latest_walk_forward_run(sleeve)
    except Exception:
        wf_raw = None

    pairs_raw = None
    try:
        from services.pairs_research_store import load_latest_pairs_run

        pairs_raw = load_latest_pairs_run()
    except Exception:
        pairs_raw = None

    resolved, unresolved = _prediction_counts()
    feedback_rec = _feedback_by_recommendation()

    jobs_card = build_jobs_last_run()
    failed_jobs = 0
    if jobs_card.warnings:
        for w in jobs_card.warnings:
            if "failed" in w.lower():
                try:
                    failed_jobs = int("".join(ch for ch in w if ch.isdigit()) or "0")
                except ValueError:
                    failed_jobs = 1

    factor_ic_stale = bool(evidence.factor_ic.stale)
    wf_stale = bool(evidence.walk_forward.stale)

    findings = build_research_brief(
        sleeve=sleeve,
        factor_ic_rows=ic_rows,
        factor_ic_history=ic_hist,
        walk_forward=wf_raw,
        pairs_summary=pairs_raw,
        predictions_resolved=resolved,
        predictions_unresolved=unresolved,
        feedback_by_rec=feedback_rec,
        data_freshness=freshness,
        factor_ic_stale=factor_ic_stale,
        walk_forward_stale=wf_stale,
        jobs_failed=failed_jobs,
    )

    open_ideas = list_ideas(sleeve=sleeve, limit=20)
    recommended = sorted(
        [i for i in open_ideas.ideas if i.status in ("new", "saved", "ready_to_test")],
        key=lambda x: (-x.priority, -x.confidence),
    )[:6]

    runs = list_runs(sleeve=sleeve, limit=1, backfill=False)
    latest_run = runs.runs[0] if runs.runs else None

    major_warnings: list[str] = []
    for card in (evidence.factor_ic, evidence.walk_forward, evidence.predictions, evidence.pairs, evidence.jobs):
        major_warnings.extend(card.warnings or [])
        if card.stale and card.stale_reason:
            major_warnings.append(card.stale_reason)
    major_warnings = list(dict.fromkeys(major_warnings))[:12]

    return ResearchOverviewResponse(
        generated_at=_utcnow_iso(),
        sleeve=sleeve,
        research_confidence_status=conf_status,
        research_confidence_score=conf_score,
        data_freshness=freshness,
        strategy_version=strategy_v,
        factor_model_version=factor_v,
        market_regime=regime,
        latest_experiment=_latest_experiment(),
        latest_completed_run=latest_run,
        predictions_resolved=resolved,
        predictions_unresolved=unresolved,
        failed_or_blocked_jobs=failed_jobs,
        factor_ic=evidence.factor_ic,
        walk_forward=evidence.walk_forward,
        pairs=evidence.pairs,
        major_warnings=major_warnings,
        findings=findings,
        recommended_ideas=recommended,
        recent_activity=_recent_activity(sleeve),
        maintenance_actions=_maintenance_actions(),
    )
