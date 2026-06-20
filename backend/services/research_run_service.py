"""Unified research run index — adapters over existing persisted stores."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from config import FACTOR_MODEL_VERSION, STRATEGY_VERSION
from data.db_engine import get_engine
from engines.quant_models import (
    BacktestRun,
    FactorIcHistory,
    JobQueueItem,
    PairsResearchRun,
    ResearchRunIndex,
)
from models.schemas_research import (
    ResearchRunCompareResponse,
    ResearchRunListResponse,
    ResearchRunMetric,
    ResearchRunSummary,
    ResultReference,
)
from services.evidence_impact_policy import default_impact_for_run_type, evaluate_evidence_impact
from services.major_evidence_gate import evaluate_major_evidence_gate
from services.research_json import json_dumps, json_loads
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MIN_EFFECT_IC = 0.02


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_dt(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _row_to_summary(row: ResearchRunIndex) -> ResearchRunSummary:
    ref_raw = json_loads(row.result_reference_json, {})
    ref = ResultReference(
        store=str(ref_raw.get("store") or ""),
        run_id=str(ref_raw.get("run_id") or row.run_id),
        detail_path=ref_raw.get("detail_path"),
    )
    return ResearchRunSummary(
        run_id=row.run_id,
        experiment_id=row.experiment_id,
        idea_id=row.idea_id,
        run_type=row.run_type,
        name=row.name or row.run_id,
        status=row.status,  # type: ignore[arg-type]
        verdict=row.verdict,
        evidence_impact=row.evidence_impact,  # type: ignore[arg-type]
        reliability=json_loads(row.reliability_json, None),
        sleeve=row.sleeve,
        universe=json_loads(row.universe_json, []),
        parameters=json_loads(row.parameters_json, {}),
        strategy_version=row.strategy_version or "",
        factor_model_version=row.factor_model_version or "",
        data_cutoff=row.data_cutoff,
        sample_size=row.sample_size,
        primary_metrics=[
            ResearchRunMetric(label=str(m.get("label", "")), value=m.get("value", ""))
            for m in json_loads(row.primary_metrics_json, [])
            if isinstance(m, dict)
        ],
        warnings=json_loads(row.warnings_json, []),
        blockers=json_loads(row.blockers_json, []),
        started_at=row.started_at,
        completed_at=row.completed_at,
        result_reference=ref,
    )


def upsert_run_index(
    summary: ResearchRunSummary,
    *,
    merge_warnings: bool = False,
) -> ResearchRunSummary:
    """Persist or update a thin index row."""
    engine = get_engine()
    now = _utcnow()
    with Session(engine) as session:
        existing = session.get(ResearchRunIndex, summary.run_id)
        warnings = summary.warnings
        if merge_warnings and existing:
            warnings = sorted(set(json_loads(existing.warnings_json, []) + warnings))

        payload = dict(
            run_id=summary.run_id,
            experiment_id=summary.experiment_id,
            idea_id=summary.idea_id,
            run_type=summary.run_type,
            name=summary.name,
            status=summary.status,
            verdict=summary.verdict,
            evidence_impact=summary.evidence_impact,
            reliability_json=json_dumps(summary.reliability) if summary.reliability else None,
            sleeve=summary.sleeve,
            universe_json=json_dumps(summary.universe),
            parameters_json=json_dumps(summary.parameters),
            strategy_version=summary.strategy_version or STRATEGY_VERSION,
            factor_model_version=summary.factor_model_version or FACTOR_MODEL_VERSION,
            data_cutoff=summary.data_cutoff,
            sample_size=summary.sample_size,
            primary_metrics_json=json_dumps([m.model_dump() for m in summary.primary_metrics]),
            warnings_json=json_dumps(warnings),
            blockers_json=json_dumps(summary.blockers),
            result_reference_json=json_dumps(summary.result_reference.model_dump()),
            started_at=summary.started_at,
            completed_at=summary.completed_at or now,
            updated_at=now,
        )
        if existing:
            for key, val in payload.items():
                if key != "run_id":
                    setattr(existing, key, val)
        else:
            session.add(ResearchRunIndex(**payload, created_at=now))
        session.commit()
    return summary


def _apply_gate(summary: ResearchRunSummary, detail: dict[str, Any]) -> ResearchRunSummary:
    gate = evaluate_major_evidence_gate(
        run_type=summary.run_type,
        summary=detail,
        parameters=summary.parameters,
        warnings=summary.warnings,
        blockers=summary.blockers,
    )
    evaluation = evaluate_evidence_impact(
        proposed_impact=gate.impact_level,
        gate_review_required=gate.review_required,
        integrity_blocked=bool(gate.blocking_checks),
    )
    summary.evidence_impact = evaluation.impact_level
    if gate.blocking_checks:
        summary.blockers = sorted(set(summary.blockers + gate.blocking_checks))
    summary.verdict = summary.verdict or ("blocked" if gate.blocking_checks else None)
    return summary


def adapter_walk_forward(run_id: str, row: BacktestRun | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = row or session.get(BacktestRun, run_id)
        if not row or row.run_type != "walk_forward_research":
            return None
        config = json.loads(row.config_json or "{}")
        metrics = json.loads(row.metrics_json or "{}")
        agg = metrics.get("aggregate_horizons") or {}
        primary_h = str((metrics.get("forward_horizons") or [20])[0])
        h_stats = agg.get(primary_h) or {}
        mean_ic = h_stats.get("mean_rank_ic")
        primary: list[ResearchRunMetric] = []
        if mean_ic is not None:
            primary.append(ResearchRunMetric(label=f"Mean rank IC ({primary_h}d)", value=round(float(mean_ic), 4)))
        primary.append(ResearchRunMetric(label="Periods scored", value=int(metrics.get("periods_scored") or 0)))

        summary = ResearchRunSummary(
            run_id=row.run_id,
            run_type="walk_forward",
            name=f"Walk-forward {config.get('sleeve', '')} {config.get('start_date', '')}–{config.get('end_date', '')}".strip(),
            status=metrics.get("status") or "completed",  # type: ignore[arg-type]
            sleeve=config.get("sleeve"),
            universe=[],
            parameters=config,
            strategy_version=metrics.get("strategy_version") or STRATEGY_VERSION,
            factor_model_version=metrics.get("factor_model_version") or FACTOR_MODEL_VERSION,
            data_cutoff=config.get("end_date"),
            sample_size=int(metrics.get("periods_scored") or 0),
            primary_metrics=primary,
            warnings=[],
            blockers=[],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(
                store="backtest_runs",
                run_id=row.run_id,
                detail_path=f"/research/walk-forward/{row.run_id}",
            ),
            evidence_impact=default_impact_for_run_type("walk_forward"),
        )
        detail = {**metrics, **config, "finished_at": row.finished_at.isoformat() if row.finished_at else None}
        return _apply_gate(summary, detail)


def adapter_pairs(run_id: str, row: PairsResearchRun | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = row or session.get(PairsResearchRun, run_id)
        if not row:
            return None
        config = json.loads(row.config_json or "{}")
        summary_data = json.loads(row.summary_json or "{}")
        symbols = config.get("symbols_used") or summary_data.get("symbols_used") or []
        primary = [
            ResearchRunMetric(label="Qualifying pairs", value=int(summary_data.get("cointegrated_count") or 0)),
            ResearchRunMetric(label="Pairs returned", value=int(summary_data.get("pairs_returned") or 0)),
        ]
        warnings: list[str] = []
        if not summary_data.get("statsmodels_available"):
            warnings.append("statsmodels_unavailable")

        summary = ResearchRunSummary(
            run_id=row.run_id,
            run_type="pairs",
            name=f"Pairs research ({summary_data.get('lookback_period', '1y')})",
            status=row.status or "completed",  # type: ignore[arg-type]
            sleeve=None,
            universe=list(symbols),
            parameters={**config, **{k: v for k, v in summary_data.items() if k != "pairs"}},
            strategy_version=STRATEGY_VERSION,
            factor_model_version=FACTOR_MODEL_VERSION,
            data_cutoff=None,
            sample_size=int(summary_data.get("pairs_returned") or 0),
            primary_metrics=primary,
            warnings=warnings,
            blockers=[row.error_message] if row.error_message else [],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(
                store="pairs_research_runs",
                run_id=row.run_id,
                detail_path=f"/research/pairs/{row.run_id}",
            ),
            evidence_impact=default_impact_for_run_type("pairs"),
        )
        return _apply_gate(summary, summary_data)


def adapter_factor_ic_panel(sleeve: str, as_of_date: str) -> ResearchRunSummary | None:
    run_id = f"ic_panel:{sleeve}:{as_of_date}"
    engine = get_engine()
    with Session(engine) as session:
        rows = (
            session.query(FactorIcHistory)
            .filter(FactorIcHistory.sleeve == sleeve, FactorIcHistory.as_of_date == as_of_date)
            .all()
        )
        if not rows:
            return None
        ics = [float(r.ic) for r in rows if r.ic is not None]
        mean_ic = round(sum(ics) / len(ics), 4) if ics else None
        sample_n = sum(int(r.sample_n or 0) for r in rows)
        primary: list[ResearchRunMetric] = []
        if mean_ic is not None:
            primary.append(ResearchRunMetric(label="Mean IC", value=mean_ic))
        primary.append(ResearchRunMetric(label="Factors", value=len({r.factor_id for r in rows})))

        summary = ResearchRunSummary(
            run_id=run_id,
            run_type="factor_ic_panel",
            name=f"Factor IC panel {sleeve} {as_of_date}",
            status="completed",
            sleeve=sleeve,
            universe=[],
            parameters={"sleeve": sleeve, "as_of_date": as_of_date},
            strategy_version=STRATEGY_VERSION,
            factor_model_version=FACTOR_MODEL_VERSION,
            data_cutoff=as_of_date,
            sample_size=sample_n or None,
            primary_metrics=primary,
            warnings=[],
            blockers=[],
            started_at=None,
            completed_at=_parse_dt(as_of_date),
            result_reference=ResultReference(
                store="factor_ic_history",
                run_id=run_id,
                detail_path=f"/api/v2/factors/performance?sleeve={sleeve}",
            ),
            evidence_impact=default_impact_for_run_type("factor_ic_panel"),
        )
        detail = {"as_of_date": as_of_date, "mean_ic": mean_ic, "sample_n": sample_n, "sample_size": sample_n}
        positive = mean_ic is not None and mean_ic >= MIN_EFFECT_IC
        gate = evaluate_major_evidence_gate(
            run_type="factor_ic_panel",
            summary=detail,
            parameters=summary.parameters,
            warnings=summary.warnings,
            blockers=summary.blockers,
            positive_direction=positive if mean_ic is not None else None,
        )
        evaluation = evaluate_evidence_impact(
            proposed_impact=gate.impact_level,
            gate_review_required=gate.review_required,
            integrity_blocked=bool(gate.blocking_checks),
        )
        summary.evidence_impact = evaluation.impact_level
        return summary


def adapter_prediction_outcomes(batch_id: str = "latest") -> ResearchRunSummary | None:
    from engines.quant_models import PredictionSnapshot

    engine = get_engine()
    with Session(engine) as session:
        snap_count = session.query(PredictionSnapshot).count()
        if snap_count == 0:
            return None
        try:
            from services.trade_feedback_service import feedback_summary

            fb = feedback_summary()
        except Exception:
            fb = {"outcomes_count": 0, "mean_prediction_error_pct": None}

        outcomes = int(fb.get("outcomes_count") or 0)
        mean_err = fb.get("mean_prediction_error_pct")
        run_id = f"prediction_outcomes:{batch_id}"
        primary: list[ResearchRunMetric] = []
        if mean_err is not None:
            primary.append(ResearchRunMetric(label="Mean forecast error %", value=round(float(mean_err), 2)))
        primary.append(ResearchRunMetric(label="Outcomes resolved", value=outcomes))

        summary = ResearchRunSummary(
            run_id=run_id,
            run_type="prediction_outcomes",
            name="Prediction outcome calibration",
            status="completed" if outcomes > 0 else "pending",  # type: ignore[arg-type]
            sleeve=None,
            universe=[],
            parameters={"batch_id": batch_id},
            strategy_version=STRATEGY_VERSION,
            factor_model_version=FACTOR_MODEL_VERSION,
            data_cutoff=None,
            sample_size=outcomes or snap_count,
            primary_metrics=primary,
            warnings=[],
            blockers=[],
            result_reference=ResultReference(
                store="prediction_snapshots",
                run_id=run_id,
                detail_path="/api/v2/feedback/summary",
            ),
            evidence_impact=default_impact_for_run_type("prediction_outcomes"),
        )
        detail = {"outcomes_count": outcomes, "mean_prediction_error_pct": mean_err, "sample_size": outcomes}
        return _apply_gate(summary, detail)


def adapter_portfolio_policy(run_id: str) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(BacktestRun, run_id)
        if not row or row.run_type not in ("institutional_policy", "portfolio_policy"):
            return None
        config = json.loads(row.config_json or "{}")
        metrics = json.loads(row.metrics_json or "{}")
        primary = [
            ResearchRunMetric(label="Total return %", value=metrics.get("total_return_pct", "—")),
            ResearchRunMetric(label="Max drawdown %", value=metrics.get("max_drawdown_pct", "—")),
        ]
        summary = ResearchRunSummary(
            run_id=row.run_id,
            run_type="portfolio_policy",
            name=f"Portfolio policy backtest ({config.get('policy', 'policy')})",
            status="completed",
            sleeve=None,
            universe=list(config.get("symbols_used") or []),
            parameters=config,
            strategy_version=STRATEGY_VERSION,
            factor_model_version=FACTOR_MODEL_VERSION,
            data_cutoff=config.get("lookback_period"),
            sample_size=len(config.get("symbols_used") or []),
            primary_metrics=primary,
            warnings=[],
            blockers=[],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(
                store="backtest_runs",
                run_id=row.run_id,
                detail_path=f"/api/v2/backtest/portfolio",
            ),
            evidence_impact=default_impact_for_run_type("portfolio_policy"),
        )
        return _apply_gate(summary, {**metrics, **config})


def adapter_similar_signal(run_id: str) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(BacktestRun, run_id)
        if not row or row.run_type != "similar_signal":
            return None
        config = json.loads(row.config_json or "{}")
        metrics = json.loads(row.metrics_json or "{}")
        sample_n = int(metrics.get("sample_n") or 0)
        primary = [ResearchRunMetric(label="Sample n", value=sample_n)]
        if metrics.get("avg_forward_return_pct") is not None:
            primary.append(
                ResearchRunMetric(label="Avg forward return %", value=metrics["avg_forward_return_pct"])
            )
        summary = ResearchRunSummary(
            run_id=row.run_id,
            run_type="similar_signal",
            name=f"Similar signal {config.get('symbol', '')}".strip(),
            status="completed",
            sleeve=config.get("sleeve"),
            universe=[config.get("symbol")] if config.get("symbol") else [],
            parameters=config,
            strategy_version=STRATEGY_VERSION,
            factor_model_version=FACTOR_MODEL_VERSION,
            data_cutoff=None,
            sample_size=sample_n,
            primary_metrics=primary,
            warnings=[],
            blockers=[],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(
                store="backtest_runs",
                run_id=row.run_id,
                detail_path=f"/api/v2/similar-signal/{config.get('symbol', '')}",
            ),
            evidence_impact=default_impact_for_run_type("similar_signal"),
        )
        return _apply_gate(summary, {**metrics, **config})


def adapter_quant_job(job_id: str, row: JobQueueItem | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = row or session.get(JobQueueItem, job_id)
        if not row:
            return None
        payload = json.loads(row.payload_json or "{}")
        summary = ResearchRunSummary(
            run_id=row.job_id,
            run_type="quant_job",
            name=row.job_name,
            status=row.status if row.status in ("pending", "running", "completed", "failed", "cancelled") else "completed",  # type: ignore[arg-type]
            sleeve=None,
            universe=[],
            parameters=payload,
            strategy_version=row.strategy_version or STRATEGY_VERSION,
            factor_model_version=row.factor_model_version or FACTOR_MODEL_VERSION,
            data_cutoff=None,
            sample_size=None,
            primary_metrics=[ResearchRunMetric(label="Job", value=row.job_name)],
            warnings=[],
            blockers=[row.error_message] if row.error_message else [],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(store="job_queue", run_id=row.job_id),
            evidence_impact=default_impact_for_run_type("quant_job"),
        )
        if row.status == "failed":
            summary.blockers.append("job_failed")
        return summary


def index_run_from_store(run_id: str, store: str | None = None) -> ResearchRunSummary | None:
    """Build summary from a persisted store and upsert index."""
    summary: ResearchRunSummary | None = None
    if store == "backtest_runs" or store is None:
        engine = get_engine()
        with Session(engine) as session:
            row = session.get(BacktestRun, run_id)
            if row:
                if row.run_type == "walk_forward_research":
                    summary = adapter_walk_forward(run_id, row)
                elif row.run_type in ("institutional_policy", "portfolio_policy"):
                    summary = adapter_portfolio_policy(run_id)
                elif row.run_type == "similar_signal":
                    summary = adapter_similar_signal(run_id)
    if summary is None and (store == "pairs_research_runs" or store is None):
        summary = adapter_pairs(run_id)
    if summary is None and (store == "job_queue" or store is None):
        summary = adapter_quant_job(run_id)
    if summary is None and store and store.startswith("ic_panel:"):
        parts = run_id.split(":")
        if len(parts) >= 3:
            summary = adapter_factor_ic_panel(parts[1], parts[2])
    if summary:
        upsert_run_index(summary)
    return summary


def backfill_run_index(*, limit: int = 200) -> int:
    """Index existing persisted runs — idempotent."""
    count = 0
    engine = get_engine()
    with Session(engine) as session:
        wf_rows = (
            session.query(BacktestRun)
            .filter(BacktestRun.run_type == "walk_forward_research")
            .order_by(BacktestRun.finished_at.desc())
            .limit(limit)
            .all()
        )
        for row in wf_rows:
            s = adapter_walk_forward(row.run_id, row)
            if s:
                upsert_run_index(s)
                count += 1

        pair_rows = (
            session.query(PairsResearchRun)
            .order_by(PairsResearchRun.finished_at.desc())
            .limit(limit)
            .all()
        )
        for row in pair_rows:
            s = adapter_pairs(row.run_id, row)
            if s:
                upsert_run_index(s)
                count += 1

        policy_rows = (
            session.query(BacktestRun)
            .filter(BacktestRun.run_type.in_(("institutional_policy", "portfolio_policy", "similar_signal")))
            .order_by(BacktestRun.finished_at.desc())
            .limit(limit)
            .all()
        )
        for row in policy_rows:
            s = adapter_portfolio_policy(row.run_id) if row.run_type != "similar_signal" else adapter_similar_signal(row.run_id)
            if s:
                upsert_run_index(s)
                count += 1

        ic_dates = (
            session.query(FactorIcHistory.sleeve, FactorIcHistory.as_of_date)
            .distinct()
            .order_by(FactorIcHistory.as_of_date.desc())
            .limit(limit)
            .all()
        )
        for sleeve, as_of in ic_dates:
            s = adapter_factor_ic_panel(sleeve, as_of)
            if s:
                upsert_run_index(s)
                count += 1

    s = adapter_prediction_outcomes()
    if s:
        upsert_run_index(s)
        count += 1

    return count


def get_run(run_id: str) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if row:
            return _row_to_summary(row)
    indexed = index_run_from_store(run_id)
    if indexed:
        return indexed
    if run_id.startswith("ic_panel:"):
        parts = run_id.split(":")
        if len(parts) >= 3:
            s = adapter_factor_ic_panel(parts[1], parts[2])
            if s:
                upsert_run_index(s)
                return s
    if run_id.startswith("prediction_outcomes:"):
        batch = run_id.split(":", 1)[-1] if ":" in run_id else "latest"
        s = adapter_prediction_outcomes(batch)
        if s:
            upsert_run_index(s)
            return s
    return None


def list_runs(
    *,
    run_type: str | None = None,
    sleeve: str | None = None,
    status: str | None = None,
    experiment_id: str | None = None,
    idea_id: str | None = None,
    offset: int = 0,
    limit: int = 50,
    backfill: bool = True,
) -> ResearchRunListResponse:
    if backfill:
        try:
            backfill_run_index(limit=max(limit, 50))
        except Exception as exc:
            logger.debug("run index backfill skipped: %s", exc)

    engine = get_engine()
    with Session(engine) as session:
        q = session.query(ResearchRunIndex)
        if run_type:
            q = q.filter(ResearchRunIndex.run_type == run_type)
        if sleeve:
            q = q.filter(ResearchRunIndex.sleeve == sleeve)
        if status:
            q = q.filter(ResearchRunIndex.status == status)
        if experiment_id:
            q = q.filter(ResearchRunIndex.experiment_id == experiment_id)
        if idea_id:
            q = q.filter(ResearchRunIndex.idea_id == idea_id)
        total = q.count()
        rows = (
            q.order_by(ResearchRunIndex.completed_at.desc().nullslast(), ResearchRunIndex.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ResearchRunListResponse(
            runs=[_row_to_summary(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def compare_runs(run_ids: list[str]) -> ResearchRunCompareResponse:
    runs: list[ResearchRunSummary] = []
    notes: list[str] = []
    for rid in run_ids:
        s = get_run(rid)
        if s:
            runs.append(s)
        else:
            notes.append(f"run_not_found:{rid}")

    sleeves = {r.sleeve for r in runs if r.sleeve}
    types = {r.run_type for r in runs}
    shared_sleeve = next(iter(sleeves)) if len(sleeves) == 1 else None
    comparable = len(runs) >= 2 and (len(sleeves) <= 1 or len(types) == 1)

    if len(types) > 1:
        notes.append("mixed_run_types")
    if len(sleeves) > 1:
        notes.append("mixed_sleeves")

    return ResearchRunCompareResponse(
        run_ids=run_ids,
        comparable=comparable,
        comparison_notes=notes,
        runs=runs,
        shared_sleeve=shared_sleeve,
        shared_run_types=sorted(types),
    )


def notify_run_persisted(run_id: str, store: str | None = None) -> None:
    """Best-effort index update after a source store persists a run."""
    try:
        index_run_from_store(run_id, store=store)
    except Exception as exc:
        logger.debug("run index notify failed for %s: %s", run_id, exc)


def link_run_to_experiment(run_id: str, experiment_id: str | None, idea_id: str | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        if not row:
            summary = get_run(run_id)
            if not summary:
                return None
            upsert_run_index(summary)
            row = session.get(ResearchRunIndex, run_id)
        if not row:
            return None
        row.experiment_id = experiment_id
        if idea_id is not None:
            row.idea_id = idea_id
        row.updated_at = _utcnow()
        session.commit()
        session.refresh(row)
        return _row_to_summary(row)
