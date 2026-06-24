"""Model Monitor aggregation — factor, prediction, data health, jobs, configuration."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from buckets import DEFAULT_BUCKET, ALL_BUCKETS
from config import (
    DYNAMIC_WEIGHTS_ENABLED,
    PREDICTION_SNAPSHOTS_ENABLED,
    QUANT_LAB_RESEARCH_API_ENABLED,
    SCORE_ENGINE_V2_ENABLED,
    TRADE_FEEDBACK_ENABLED,
)
from data.db_engine import get_engine
from engines.quant_models import FactorIcHistory, JobQueueItem, PredictionOutcome, PredictionSnapshot, ResearchRunIndex
from models.schemas_research import (
    DataHealthSummary,
    FactorHealthItem,
    ModelConfigurationSummary,
    ModelMonitorResponse,
    PredictionHealthSummary,
    ResearchJobMonitorItem,
)
from services.trade_feedback_service import factor_admin_view, feedback_summary
from services.research_json import json_loads
from sqlalchemy import func
from sqlalchemy.orm import Session


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _horizon_stability(factor_id: str, sleeve: str) -> str:
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(FactorIcHistory.horizon_days, func.avg(FactorIcHistory.ic))
            .filter(FactorIcHistory.factor_id == factor_id, FactorIcHistory.sleeve == sleeve)
            .group_by(FactorIcHistory.horizon_days)
            .all()
        )
    if len(rows) <= 1:
        return "single_horizon"
    ics = [float(r[1]) for r in rows if r[1] is not None]
    if not ics:
        return "unknown"
    same_sign = all(i >= 0 for i in ics) or all(i <= 0 for i in ics)
    return "stable" if same_sign else "mixed"


def get_factor_health(sleeve: str) -> list[FactorHealthItem]:
    admin = factor_admin_view(sleeve)
    weights: dict[str, float] = {}
    try:
        from engines.weighting.weight_store import WeightStore

        weights = WeightStore.load(sleeve)
    except Exception:
        pass

    recent_cutoff = (date.today() - timedelta(days=30)).isoformat()
    long_cutoff = (date.today() - timedelta(days=180)).isoformat()
    engine = get_engine()
    items: list[FactorHealthItem] = []

    with Session(engine) as session:
        for f in admin.get("factors") or []:
            factor_id = f["factor_id"]
            recent = (
                session.query(func.avg(FactorIcHistory.ic), func.max(FactorIcHistory.sample_n))
                .filter(
                    FactorIcHistory.factor_id == factor_id,
                    FactorIcHistory.sleeve == sleeve,
                    FactorIcHistory.as_of_date >= recent_cutoff,
                )
                .first()
            )
            long_term = (
                session.query(func.avg(FactorIcHistory.ic))
                .filter(
                    FactorIcHistory.factor_id == factor_id,
                    FactorIcHistory.sleeve == sleeve,
                    FactorIcHistory.as_of_date >= long_cutoff,
                )
                .scalar()
            )
            last_row = (
                session.query(FactorIcHistory)
                .filter(FactorIcHistory.factor_id == factor_id, FactorIcHistory.sleeve == sleeve)
                .order_by(FactorIcHistory.as_of_date.desc())
                .first()
            )
            last_run = (
                session.query(ResearchRunIndex.run_id)
                .filter(
                    ResearchRunIndex.sleeve == sleeve,
                    ResearchRunIndex.run_type.in_(("walk_forward", "factor_ic_panel")),
                    ResearchRunIndex.status == "completed",
                )
                .order_by(ResearchRunIndex.completed_at.desc())
                .first()
            )
            recent_ic = float(recent[0]) if recent and recent[0] is not None else None
            long_ic = float(long_term) if long_term is not None else None
            drift = round(recent_ic - long_ic, 4) if recent_ic is not None and long_ic is not None else None

            items.append(
                FactorHealthItem(
                    factor_id=factor_id,
                    display_name=f.get("display_name") or factor_id,
                    lifecycle=f.get("recommended_action") or "hold",
                    production_weight=weights.get(factor_id),
                    recent_ic=round(recent_ic, 4) if recent_ic is not None else None,
                    long_term_ic=round(long_ic, 4) if long_ic is not None else None,
                    sample_size=int(recent[1]) if recent and recent[1] is not None else None,
                    drift=drift,
                    horizon_stability=_horizon_stability(factor_id, sleeve),
                    regime_stability="regime_metadata_available",
                    factor_version=f.get("formula_version") or "",
                    transformation_lineage="percentile_0_100 · mad_3sigma",
                    last_calculation=last_row.as_of_date if last_row else None,
                    last_reliable_validation_run_id=last_run[0] if last_run else None,
                    supporting_run_ids=[last_run[0]] if last_run else [],
                )
            )
    return items


def get_prediction_health() -> PredictionHealthSummary:
    fb = feedback_summary()
    engine = get_engine()
    with Session(engine) as session:
        resolved = session.query(PredictionOutcome).count()
        snapshots = session.query(PredictionSnapshot).count()
        stale_cutoff = _utcnow() - timedelta(days=45)
        stale = (
            session.query(PredictionSnapshot)
            .outerjoin(PredictionOutcome, PredictionOutcome.prediction_id == PredictionSnapshot.id)
            .filter(PredictionSnapshot.created_at < stale_cutoff, PredictionOutcome.prediction_id.is_(None))
            .count()
        )
        unresolved = max(0, snapshots - resolved)
        latest_job = (
            session.query(JobQueueItem)
            .filter(JobQueueItem.job_name.in_(("resolve-outcomes", "resolve_outcomes", "forward-labels")))
            .order_by(JobQueueItem.created_at.desc())
            .first()
        )

    coverage = round(100.0 * resolved / snapshots, 1) if snapshots else None
    outcomes = fb.get("recent_outcomes") or []
    rec_counts: dict[str, int] = {}
    for o in outcomes:
        rec = str(o.get("recommendation") or "unknown")
        rec_counts[rec] = rec_counts.get(rec, 0) + 1

    return PredictionHealthSummary(
        resolved_count=resolved,
        unresolved_count=unresolved,
        stale_count=stale,
        coverage_pct=coverage,
        mean_forecast_error_pct=fb.get("mean_prediction_error_pct"),
        recommendation_outcomes=rec_counts,
        horizon_breakdown={"default_horizon_days": 20},
        regime_breakdown={},
        latest_outcome_job={
            "job_id": latest_job.job_id,
            "status": latest_job.status,
            "finished_at": latest_job.finished_at.isoformat() if latest_job and latest_job.finished_at else None,
        }
        if latest_job
        else None,
        calibration_ready=resolved >= 30 and coverage is not None and coverage >= 50.0,
    )


def get_data_health(sleeve: str) -> DataHealthSummary:
    blockers: list[str] = []
    try:
        from data.db_engine import get_engine as ge
        from engines.quant_models import ResearchRunIndex
        from sqlalchemy.orm import Session as S

        with S(ge()) as session:
            rows = (
                session.query(ResearchRunIndex)
                .filter(ResearchRunIndex.evidence_impact == "integrity_blocker")
                .order_by(ResearchRunIndex.completed_at.desc())
                .limit(10)
                .all()
            )
            blockers = [
                f"{r.run_id}:{','.join(json_loads(r.warnings_json, []))}" for r in rows
            ]
    except Exception:
        pass

    return DataHealthSummary(
        provider_availability={"fmp": True, "finnhub": True},
        price_freshness={"sleeve": sleeve, "status": "see_scan_health"},
        missing_stocks=[],
        stale_stocks=[],
        reconciliation_issues=[],
        data_confidence={"note": "Use scan reconcile flags for symbol-level detail"},
        excluded_stock_counts={"research_excluded": 0},
        integrity_blockers=blockers,
    )


def get_research_jobs(limit: int = 30) -> list[ResearchJobMonitorItem]:
    engine = get_engine()
    items: list[ResearchJobMonitorItem] = []
    with Session(engine) as session:
        rows = session.query(JobQueueItem).order_by(JobQueueItem.created_at.desc()).limit(limit).all()
        for row in rows:
            payload: dict[str, Any] = {}
            try:
                import json

                payload = json.loads(row.payload_json or "{}")
            except Exception:
                payload = {}
            duration = None
            if row.started_at and row.finished_at:
                duration = int((row.finished_at - row.started_at).total_seconds())
            dup = (
                session.query(JobQueueItem)
                .filter(
                    JobQueueItem.job_name == row.job_name,
                    JobQueueItem.status.in_(("pending", "running")),
                    JobQueueItem.job_id != row.job_id,
                )
                .count()
                > 0
            )
            items.append(
                ResearchJobMonitorItem(
                    job_id=row.job_id,
                    job_name=row.job_name,
                    status=row.status,
                    stage=row.status,
                    duration_seconds=duration,
                    experiment_id=payload.get("experiment_id"),
                    run_id=payload.get("run_id"),
                    error_message=row.error_message,
                    error_details={"payload": payload},
                    created_at=row.created_at.isoformat() if row.created_at else None,
                    started_at=row.started_at.isoformat() if row.started_at else None,
                    finished_at=row.finished_at.isoformat() if row.finished_at else None,
                    retry_blocked=dup,
                )
            )
    return items


def get_model_configuration() -> ModelConfigurationSummary:
    from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
    from engines.weighting.weight_store import WeightStore

    regime = None
    try:
        regime = WeightStore.current_regime()
    except Exception:
        pass

    weights_by_sleeve: dict[str, dict[str, float]] = {}
    for sleeve_name in ALL_BUCKETS:
        try:
            weights_by_sleeve[sleeve_name] = WeightStore.load(sleeve_name, regime=regime)
        except Exception:
            weights_by_sleeve[sleeve_name] = {}

    return ModelConfigurationSummary(
        strategy_version=STRATEGY_VERSION,
        factor_model_version=FACTOR_MODEL_VERSION,
        current_regime=regime,
        dynamic_weights_enabled=bool(DYNAMIC_WEIGHTS_ENABLED),
        weights_by_sleeve=weights_by_sleeve,
        enabled_research_features={
            "score_engine_v2": bool(SCORE_ENGINE_V2_ENABLED),
            "prediction_snapshots": bool(PREDICTION_SNAPSHOTS_ENABLED),
            "trade_feedback": bool(TRADE_FEEDBACK_ENABLED),
            "quant_lab_research_api": bool(QUANT_LAB_RESEARCH_API_ENABLED),
        },
        read_only=True,
    )


def get_model_monitor(sleeve: str | None = None) -> ModelMonitorResponse:
    sleeve = sleeve or DEFAULT_BUCKET
    return ModelMonitorResponse(
        sleeve=sleeve,
        factor_health=get_factor_health(sleeve),
        prediction_health=get_prediction_health(),
        data_health=get_data_health(sleeve),
        research_jobs=get_research_jobs(),
        model_configuration=get_model_configuration(),
    )
