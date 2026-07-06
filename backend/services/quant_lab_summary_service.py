"""Read-only Quant Lab evidence summaries — latest persisted runs, no heavy jobs."""
from __future__ import annotations

import json
from buckets import DEFAULT_BUCKET
from datetime import date, datetime, timezone
from typing import Any

from config import SCORE_ENGINE_V2_ENABLED, TRADE_FEEDBACK_ENABLED
from data.db_engine import get_engine
from engines.quant_models import BacktestRun, FactorIcHistory, JobQueueItem, PredictionSnapshot
from models.schemas_v2 import QuantLabEvidenceResponse, QuantLabLastRunSummary, QuantLabMainMetric
from sqlalchemy.orm import Session

IC_STALE_DAYS = 7
WALK_FORWARD_STALE_DAYS = 30
PREDICTIONS_STALE_DAYS = 14
JOBS_ATTENTION_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _days_since(value: str | date | datetime | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        dt = datetime.combine(value, datetime.min.time())
    elif isinstance(value, datetime):
        dt = value.replace(tzinfo=None)
    else:
        dt = _parse_dt(str(value))
    if dt is None:
        return None
    return (_utcnow() - dt).total_seconds() / 86400.0


def _unavailable(
    summary_id: str,
    *,
    reason: str,
    tab: str | None = None,
    research_only: bool = False,
    trust_indicator: str = "no_saved_run",
) -> QuantLabLastRunSummary:
    return QuantLabLastRunSummary(
        id=summary_id,
        available=False,
        reason=reason,
        trust_indicator=trust_indicator,
        research_only=research_only,
        tab=tab,
    )


def load_latest_walk_forward_run(sleeve: str | None = None) -> dict[str, Any] | None:
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(BacktestRun)
            .filter(BacktestRun.run_type == "walk_forward_research")
            .order_by(BacktestRun.finished_at.desc())
            .limit(50)
            .all()
        )
        for row in rows:
            config = json.loads(row.config_json or "{}")
            if sleeve and config.get("sleeve") != sleeve:
                continue
            summary = json.loads(row.metrics_json or "{}")
            return {
                "run_id": row.run_id,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                **summary,
            }
    return None


def build_walk_forward_last_run(sleeve: str = DEFAULT_BUCKET) -> QuantLabLastRunSummary:
    row = load_latest_walk_forward_run(sleeve)
    if not row:
        return _unavailable(
            "walk_forward",
            reason="No saved run found",
            tab="walk-forward",
            research_only=True,
        )

    finished_at = row.get("finished_at")
    periods_scored = int(row.get("periods_scored") or 0)
    age_days = _days_since(finished_at)
    stale = age_days is not None and age_days > WALK_FORWARD_STALE_DAYS
    stale_reason = (
        f"Last walk-forward run is {int(age_days)} days old"
        if stale and age_days is not None
        else None
    )

    agg = row.get("aggregate_horizons") or {}
    primary_h = str((row.get("forward_horizons") or [20])[0])
    h_stats = agg.get(primary_h) or {}
    mean_ic = h_stats.get("mean_rank_ic")
    main_metric = None
    if mean_ic is not None:
        main_metric = QuantLabMainMetric(label=f"Mean rank IC ({primary_h}d)", value=f"{float(mean_ic):.3f}")

    warnings: list[str] = []
    if periods_scored == 0:
        warnings.append("Last run scored zero periods")
    if stale:
        warnings.append(stale_reason or "Walk-forward evidence is stale")

    trust = "fresh"
    if periods_scored < 3:
        trust = "insufficient_sample"
    elif stale:
        trust = "stale"

    return QuantLabLastRunSummary(
        id="walk_forward",
        available=True,
        generated_at=finished_at,
        run_id=row.get("run_id"),
        sleeve=row.get("sleeve") or sleeve,
        status=row.get("status") or "completed",
        sample_size=periods_scored,
        main_metric=main_metric,
        stale=stale,
        stale_reason=stale_reason,
        warnings=warnings,
        trust_indicator=trust,
        research_only=True,
        tab="walk-forward",
    )


def build_pairs_last_run() -> QuantLabLastRunSummary:
    from services.pairs_research_store import load_latest_pairs_run

    row = load_latest_pairs_run()
    if not row:
        return _unavailable(
            "pairs",
            reason="No saved run found",
            tab="pairs",
            research_only=True,
        )

    finished_at = row.get("finished_at")
    pairs_returned = int(row.get("pairs_returned") or 0)
    cointegrated = int(row.get("cointegrated_count") or 0)
    age_days = _days_since(finished_at)
    stale = age_days is not None and age_days > WALK_FORWARD_STALE_DAYS
    stale_reason = (
        f"Last pairs run is {int(age_days)} days old"
        if stale and age_days is not None
        else None
    )

    main_metric = QuantLabMainMetric(
        label="Qualifying pairs",
        value=str(cointegrated),
    )

    warnings: list[str] = []
    if pairs_returned == 0:
        warnings.append("Last run returned zero pair rows")
    if stale:
        warnings.append(stale_reason or "Pairs evidence is stale")
    if not row.get("statsmodels_available"):
        warnings.append("statsmodels unavailable on last run")

    trust = "fresh"
    if pairs_returned < 1:
        trust = "insufficient_sample"
    elif stale:
        trust = "stale"

    return QuantLabLastRunSummary(
        id="pairs",
        available=True,
        generated_at=finished_at,
        run_id=row.get("run_id"),
        status=row.get("status") or "completed",
        sample_size=pairs_returned or None,
        main_metric=main_metric,
        stale=stale,
        stale_reason=stale_reason,
        warnings=warnings,
        trust_indicator=trust,
        research_only=True,
        tab="pairs",
    )


def build_factor_ic_last_run(sleeve: str = DEFAULT_BUCKET) -> QuantLabLastRunSummary:
    if not SCORE_ENGINE_V2_ENABLED:
        return _unavailable(
            "factor_ic",
            reason="Score engine v2 disabled",
            tab="factor-performance",
            trust_indicator="feature_disabled",
        )

    engine = get_engine()
    with Session(engine) as session:
        latest_date = (
            session.query(FactorIcHistory.as_of_date)
            .filter(FactorIcHistory.sleeve == sleeve)
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(1)
            .scalar()
        )
        if not latest_date:
            return _unavailable(
                "factor_ic",
                reason="No saved run found",
                tab="factor-performance",
            )

        rows = (
            session.query(FactorIcHistory)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date == latest_date)
            .all()
        )

    as_of = latest_date.isoformat() if hasattr(latest_date, "isoformat") else str(latest_date)
    age_days = _days_since(latest_date)
    stale = age_days is not None and age_days > IC_STALE_DAYS
    stale_reason = (
        f"Factor IC panel is {int(age_days)} days old — run IC panel job"
        if stale and age_days is not None
        else None
    )

    sample_n = sum(int(r.sample_n or 0) for r in rows)
    factor_count = len({r.factor_id for r in rows})
    ics = [float(r.ic) for r in rows if r.ic is not None]
    mean_ic = round(sum(ics) / len(ics), 4) if ics else None

    main_metric = None
    if mean_ic is not None:
        main_metric = QuantLabMainMetric(label="Mean IC", value=f"{mean_ic:.3f}")

    warnings: list[str] = []
    if stale:
        warnings.append(stale_reason or "IC data is stale")
    if factor_count == 0:
        warnings.append("No factor rows for this sleeve")

    trust = "fresh"
    if factor_count == 0 or sample_n < 30:
        trust = "insufficient_sample"
    elif stale:
        trust = "stale"

    return QuantLabLastRunSummary(
        id="factor_ic",
        available=True,
        generated_at=as_of,
        sleeve=sleeve,
        status="completed",
        sample_size=sample_n or None,
        main_metric=main_metric,
        stale=stale,
        stale_reason=stale_reason,
        warnings=warnings,
        trust_indicator=trust,
        tab="factor-performance",
    )


def build_predictions_last_run() -> QuantLabLastRunSummary:
    if not SCORE_ENGINE_V2_ENABLED or not TRADE_FEEDBACK_ENABLED:
        return _unavailable(
            "predictions",
            reason="Prediction tracking disabled",
            tab="predictions",
            trust_indicator="feature_disabled",
        )

    engine = get_engine()
    with Session(engine) as session:
        latest_snap = (
            session.query(PredictionSnapshot)
            .order_by(PredictionSnapshot.created_at.desc())
            .limit(1)
            .first()
        )
        snap_count = session.query(PredictionSnapshot).count()

    if not latest_snap or snap_count == 0:
        return _unavailable(
            "predictions",
            reason="No saved run found",
            tab="predictions",
        )

    generated_at = latest_snap.created_at.isoformat() if latest_snap.created_at else None
    age_days = _days_since(latest_snap.created_at)
    stale = age_days is not None and age_days > PREDICTIONS_STALE_DAYS
    stale_reason = (
        f"Latest snapshot is {int(age_days)} days old"
        if stale and age_days is not None
        else None
    )

    from engines.prediction.snapshots import list_recent_snapshots

    snaps = list_recent_snapshots(limit=100)
    unresolved = sum(1 for s in snaps if not s.get("outcome"))

    try:
        from services.trade_feedback_service import feedback_summary

        fb = feedback_summary()
        outcomes_count = int(fb.get("outcomes_count") or 0)
        mean_err = fb.get("mean_prediction_error_pct")
    except Exception:
        outcomes_count = 0
        mean_err = None

    main_metric = None
    if mean_err is not None:
        main_metric = QuantLabMainMetric(label="Mean forecast error", value=f"{float(mean_err):.2f}%")
    elif unresolved > 0:
        main_metric = QuantLabMainMetric(label="Unresolved", value=str(unresolved))

    warnings: list[str] = []
    if unresolved > 0:
        warnings.append(f"{unresolved} recent predictions unresolved")
    if stale:
        warnings.append(stale_reason or "Outcome evidence is stale")

    trust = "fresh"
    if outcomes_count < 5:
        trust = "insufficient_sample"
    elif stale or unresolved > 10:
        trust = "needs_attention" if unresolved > 10 else "stale"

    return QuantLabLastRunSummary(
        id="predictions",
        available=True,
        generated_at=generated_at,
        status="completed" if outcomes_count > 0 else "pending",
        sample_size=snap_count,
        main_metric=main_metric,
        stale=stale,
        stale_reason=stale_reason,
        warnings=warnings,
        trust_indicator=trust,
        tab="predictions",
    )


def build_jobs_last_run() -> QuantLabLastRunSummary:
    from data.historical_store import HistoricalStore

    scheduler_jobs = HistoricalStore().get_recent_job_logs(limit=10)
    queue_jobs = _list_recent_queue_jobs(limit=10)

    combined = scheduler_jobs + queue_jobs
    if not combined:
        return _unavailable(
            "jobs",
            reason="No saved run found",
            tab="data-quality",
        )

    def sort_key(j: dict[str, Any]) -> str:
        return j.get("finished_at") or j.get("started_at") or j.get("created_at") or ""

    combined.sort(key=sort_key, reverse=True)
    latest = combined[0]
    generated_at = (
        latest.get("finished_at") or latest.get("started_at") or latest.get("created_at")
    )

    failed_recent = [
        j
        for j in combined
        if str(j.get("status", "")).lower() in ("failed", "error")
        and (_days_since(j.get("finished_at") or j.get("started_at")) or 999)
        <= JOBS_ATTENTION_DAYS
    ]
    completed_recent = [
        j
        for j in combined
        if str(j.get("status", "")).lower() in ("completed", "done", "success")
    ]

    status = str(latest.get("status") or "unknown")
    job_name = str(latest.get("job_name") or "job")
    main_metric = QuantLabMainMetric(label="Latest job", value=f"{job_name} · {status}")

    warnings: list[str] = []
    if failed_recent:
        warnings.append(f"{len(failed_recent)} failed job(s) in the last {JOBS_ATTENTION_DAYS} days")

    trust = "fresh"
    if failed_recent:
        trust = "needs_attention"
    elif not completed_recent:
        trust = "insufficient_sample"

    return QuantLabLastRunSummary(
        id="jobs",
        available=True,
        generated_at=generated_at,
        status=status,
        sample_size=len(combined),
        main_metric=main_metric,
        stale=False,
        warnings=warnings,
        trust_indicator=trust,
        tab="data-quality",
    )


def _list_recent_queue_jobs(limit: int = 10) -> list[dict[str, Any]]:
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(JobQueueItem)
            .order_by(JobQueueItem.created_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "job_id": r.job_id,
                "job_name": r.job_name,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "error_message": r.error_message,
            }
            for r in rows
        ]


def get_quant_lab_evidence(sleeve: str = DEFAULT_BUCKET) -> QuantLabEvidenceResponse:
    from core.sleeve import normalize_sleeve

    sleeve = normalize_sleeve(sleeve)
    return QuantLabEvidenceResponse(
        sleeve=sleeve,
        generated_at=_utcnow().isoformat(),
        factor_ic=build_factor_ic_last_run(sleeve),
        walk_forward=build_walk_forward_last_run(sleeve),
        predictions=build_predictions_last_run(),
        pairs=build_pairs_last_run(),
        jobs=build_jobs_last_run(),
    )
