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
    ChartSeries,
    ExperimentValidationCheck,
    ResearchRunCompareDetailResponse,
    ResearchRunCompareResponse,
    ResearchRunListItem,
    ResearchRunListResponse,
    ResearchRunMetric,
    ResearchRunSummary,
    ResultReference,
    RunComparisonMetricDiff,
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


def _duration_seconds(row: ResearchRunIndex) -> int | None:
    if row.started_at and row.completed_at:
        return max(0, int((row.completed_at - row.started_at).total_seconds()))
    return None


def _reliability_score(row: ResearchRunIndex) -> int | None:
    rel = json_loads(row.reliability_json, None)
    if isinstance(rel, dict) and rel.get("score") is not None:
        try:
            return int(rel["score"])
        except (TypeError, ValueError):
            return None
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


def _row_to_list_item(row: ResearchRunIndex) -> ResearchRunListItem:
    summary = _row_to_summary(row)
    return ResearchRunListItem(
        **summary.model_dump(),
        duration_seconds=_duration_seconds(row),
        archived=bool(row.archived),
        research_notes=row.research_notes or "",
        reliability_score=_reliability_score(row),
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


def adapter_scan_evaluation(run_id: str, row: BacktestRun | None = None) -> ResearchRunSummary | None:
    engine = get_engine()
    with Session(engine) as session:
        row = row or session.get(BacktestRun, run_id)
        if not row or row.run_type != "scan_evaluation":
            return None
        config = json.loads(row.config_json or "{}")
        metrics = json.loads(row.metrics_json or "{}")
        ql = metrics.get("quant_lab") or {}
        primary: list[ResearchRunMetric] = []
        if ql.get("mode") == "comparison":
            table = ql.get("comparison_table") or []
            if table:
                best = max(table, key=lambda r: float(r.get("recall_at_10") or 0))
                primary.append(
                    ResearchRunMetric(
                        label="Best Recall@10",
                        value=f"{best.get('algorithm_version')}: {best.get('recall_at_10')}",
                    )
                )
        else:
            if ql.get("recall_at_10") is not None:
                primary.append(ResearchRunMetric(label="Recall@10", value=ql["recall_at_10"]))
            if ql.get("recall_at_20") is not None:
                primary.append(ResearchRunMetric(label="Recall@20", value=ql["recall_at_20"]))
        primary.append(ResearchRunMetric(label="Rebalance dates", value=int(ql.get("rebalance_count") or 0)))

        warnings = list(metrics.get("caveats") or [])[:5]
        summary = ResearchRunSummary(
            run_id=row.run_id,
            run_type="scan_evaluation",
            name=metrics.get("name") or f"Scan evaluation ({config.get('parameters', {}).get('bucket', '')})",
            status="completed",  # type: ignore[arg-type]
            sleeve=config.get("parameters", {}).get("bucket") or config.get("sleeve"),
            universe=[],
            parameters=config.get("parameters") or config,
            strategy_version=config.get("parameters", {}).get("strategy_version") or STRATEGY_VERSION,
            factor_model_version=config.get("parameters", {}).get("scoring_version") or FACTOR_MODEL_VERSION,
            data_cutoff=config.get("parameters", {}).get("end_date"),
            sample_size=int(ql.get("rebalance_count") or 0),
            primary_metrics=primary,
            warnings=warnings,
            blockers=[],
            started_at=row.started_at,
            completed_at=row.finished_at,
            result_reference=ResultReference(
                store="backtest_runs",
                run_id=row.run_id,
                detail_path=f"/research/runs/{row.run_id}",
            ),
            evidence_impact=default_impact_for_run_type("scan_evaluation"),
        )
        detail = {**metrics, **config}
        return _apply_gate(summary, detail)


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
                elif row.run_type == "scan_evaluation":
                    summary = adapter_scan_evaluation(run_id, row)
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
    verdict: str | None = None,
    evidence_impact: str | None = None,
    experiment_id: str | None = None,
    idea_id: str | None = None,
    search: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    archived: bool | None = False,
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
        if verdict:
            q = q.filter(ResearchRunIndex.verdict == verdict)
        if evidence_impact:
            q = q.filter(ResearchRunIndex.evidence_impact == evidence_impact)
        if archived is not None:
            q = q.filter(ResearchRunIndex.archived == (1 if archived else 0))
        if date_from:
            q = q.filter(ResearchRunIndex.completed_at >= _parse_dt(date_from))
        if date_to:
            q = q.filter(ResearchRunIndex.completed_at <= _parse_dt(date_to))
        if search:
            term = f"%{search.strip()}%"
            q = q.filter(
                (ResearchRunIndex.name.ilike(term))
                | (ResearchRunIndex.run_id.ilike(term))
            )
        total = q.count()
        rows = (
            q.order_by(ResearchRunIndex.completed_at.desc().nullslast(), ResearchRunIndex.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ResearchRunListResponse(
            runs=[_row_to_list_item(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )


def _compatibility_checks(runs: list[ResearchRunListItem]) -> tuple[list[ExperimentValidationCheck], list[str], bool]:
    checks: list[ExperimentValidationCheck] = []
    notes: list[str] = []
    types = {r.run_type for r in runs}
    type_ok = len(types) == 1
    checks.append(
        ExperimentValidationCheck(
            key="same_run_type",
            label="Experiment type",
            status="ok" if type_ok else "error",
            detail="All runs share the same run type" if type_ok else f"Mixed types: {', '.join(sorted(types))}",
        )
    )

    sleeves = {r.sleeve for r in runs if r.sleeve}
    sleeve_ok = len(sleeves) <= 1
    checks.append(
        ExperimentValidationCheck(
            key="sleeve",
            label="Sleeve",
            status="ok" if sleeve_ok else "warning",
            detail="Shared sleeve" if sleeve_ok else "Mixed sleeves — compare with caution",
        )
    )

    strategies = {r.strategy_version for r in runs if r.strategy_version}
    factors = {r.factor_model_version for r in runs if r.factor_model_version}
    version_ok = len(strategies) <= 1 and len(factors) <= 1
    checks.append(
        ExperimentValidationCheck(
            key="model_versions",
            label="Model versions",
            status="ok" if version_ok else "warning",
            detail="Matching strategy/factor versions" if version_ok else "Version mismatch across runs",
        )
    )

    horizons: set[str] = set()
    for r in runs:
        for h in r.parameters.get("forward_horizons") or []:
            horizons.add(str(h))
    horizon_ok = len(horizons) <= 1 or not horizons
    checks.append(
        ExperimentValidationCheck(
            key="horizons",
            label="Horizons",
            status="ok" if horizon_ok else "error",
            detail="Comparable forward horizons" if horizon_ok else f"Mixed horizons: {', '.join(sorted(horizons))}",
        )
    )

    cutoffs = [r.data_cutoff for r in runs if r.data_cutoff]
    date_ok = len(set(cutoffs)) <= 1 or len(cutoffs) == 0
    checks.append(
        ExperimentValidationCheck(
            key="date_overlap",
            label="Data window",
            status="ok" if date_ok else "warning",
            detail="Aligned data cutoffs" if date_ok else "Different data cutoffs — metrics not directly comparable",
        )
    )

    universes = {tuple(sorted(r.universe)) for r in runs if r.universe}
    universe_ok = len(universes) <= 1
    checks.append(
        ExperimentValidationCheck(
            key="universe",
            label="Universe",
            status="ok" if universe_ok else "warning",
            detail="Same universe" if universe_ok else "Universe differs between runs",
        )
    )

    comparable = type_ok and horizon_ok and len(runs) >= 2 and len(runs) <= 4
    if len(runs) < 2:
        notes.append("need_at_least_two_runs")
    if len(runs) > 4:
        notes.append("max_four_runs")
        comparable = False
    if not type_ok:
        notes.append("mixed_run_types")
    if not horizon_ok:
        notes.append("mixed_horizons")
    return checks, notes, comparable


def _scalar_export(value: Any) -> str | float | int | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value if not isinstance(value, bool) else int(value)
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _metric_diffs(runs: list[ResearchRunListItem]) -> tuple[list[RunComparisonMetricDiff], list[RunComparisonMetricDiff]]:
    param_diffs: list[RunComparisonMetricDiff] = []
    metric_diffs: list[RunComparisonMetricDiff] = []
    param_keys = sorted({k for r in runs for k in r.parameters.keys()})
    for key in param_keys[:20]:
        values = {r.run_id: _scalar_export(r.parameters.get(key)) for r in runs}
        unique = {json.dumps(v, sort_keys=True, default=str) for v in values.values()}
        param_diffs.append(
            RunComparisonMetricDiff(
                label=key,
                values=values,
                comparable=len(unique) <= 1,
                note="" if len(unique) <= 1 else "Parameter differs",
            )
        )

    labels = sorted({m.label for r in runs for m in r.primary_metrics})
    for label in labels:
        values: dict[str, str | float | int | None] = {}
        for r in runs:
            match = next((m.value for m in r.primary_metrics if m.label == label), None)
            values[r.run_id] = match
        unique_vals = {str(v) for v in values.values()}
        metric_diffs.append(
            RunComparisonMetricDiff(
                label=label,
                values=values,
                comparable=len(unique_vals) <= 1 or len(runs) == len({r.run_type for r in runs}),
                note="" if len(unique_vals) > 1 else "Identical across runs",
            )
        )
    return param_diffs, metric_diffs


def compare_runs_detail(run_ids: list[str]) -> ResearchRunCompareDetailResponse:
    items: list[ResearchRunListItem] = []
    notes: list[str] = []
    for rid in run_ids[:4]:
        summary = get_run(rid)
        if not summary:
            notes.append(f"run_not_found:{rid}")
            continue
        engine = get_engine()
        with Session(engine) as session:
            row = session.get(ResearchRunIndex, rid)
            items.append(_row_to_list_item(row) if row else ResearchRunListItem(**summary.model_dump()))

    checks, compat_notes, comparable = _compatibility_checks(items)
    notes.extend(compat_notes)
    param_diffs, metric_diffs = _metric_diffs(items) if items else ([], [])

    sleeves = {r.sleeve for r in items if r.sleeve}
    types = {r.run_type for r in items}
    conclusion = "Runs are comparable for side-by-side review." if comparable else (
        "Runs are not fully compatible — do not treat unrelated metrics as equivalents."
    )

    from services.research_run_detail_service import build_charts, load_detail_payload

    charts: list[ChartSeries] = []
    if comparable and items:
        detail = load_detail_payload(items[0])
        charts = build_charts(items[0].run_type, items[0], detail)

    return ResearchRunCompareDetailResponse(
        run_ids=[r.run_id for r in items],
        comparable=comparable,
        compatibility_checks=checks,
        comparison_notes=notes,
        parameter_diffs=param_diffs,
        metric_diffs=metric_diffs,
        runs=items,
        conclusion=conclusion,
        shared_sleeve=next(iter(sleeves)) if len(sleeves) == 1 else None,
        shared_run_types=sorted(types),
        charts=charts,
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


def refresh_run_from_store(run_id: str, store: str | None = None) -> ResearchRunListItem | None:
    summary = index_run_from_store(run_id, store=store)
    if not summary:
        return None
    from services.research_run_detail_service import get_run_detail

    get_run_detail(run_id, refresh=True, use_llm=False)
    engine = get_engine()
    with Session(engine) as session:
        row = session.get(ResearchRunIndex, run_id)
        return _row_to_list_item(row) if row else ResearchRunListItem(**summary.model_dump())


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
