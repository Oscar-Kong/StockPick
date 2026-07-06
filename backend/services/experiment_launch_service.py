"""Unified experiment launch — routes to existing quant engines without rewriting math."""
from __future__ import annotations

import json
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from config import DEMO_MODE, FACTOR_DISCOVERY_ENABLED, SCORE_ENGINE_V2_ENABLED
from models.schemas_research import ExperimentLaunchResponse, ExperimentValidateRequest
from services.experiment_job_service import (
    complete_stage,
    create_job,
    fail_job,
    get_active_job,
    get_job,
    mark_stage,
    update_job,
)
from services.experiment_presets_service import merge_parameters, preset_allows_major_evidence
from services.experiment_universe_service import resolve_universe
from services.experiment_validation_service import validate_experiment
from services.research_experiments_service import get_experiment
from services.research_ideas_service import update_idea
from services.research_run_service import link_run_to_experiment, notify_run_persisted
from models.schemas_research import ResearchIdeaUpdate

logger = logging.getLogger(__name__)
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="exp-launch")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def launch_experiment(experiment_id: str) -> ExperimentLaunchResponse:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"experiment not found: {experiment_id}")

    active = get_active_job(experiment_id)
    if active:
        return ExperimentLaunchResponse(
            job_id=active.job_id,
            experiment_id=experiment_id,
            status="running",
            duplicate_blocked=True,
            message="A job is already running for this experiment.",
        )

    if exp.experiment_type == "factor_discovery" and not bool(FACTOR_DISCOVERY_ENABLED):
        job = create_job(experiment_id, experiment_type=exp.experiment_type)
        fail_job(
            job.job_id,
            "validating",
            "Factor discovery is not enabled (FACTOR_DISCOVERY_ENABLED=false).",
            preserve_last_success=False,
        )
        return ExperimentLaunchResponse(
            job_id=job.job_id,
            experiment_id=experiment_id,
            status="failed",
            message="Factor discovery is not enabled in this release.",
        )

    validation = validate_experiment(
        ExperimentValidateRequest(
            experiment_type=exp.experiment_type,
            sleeve=exp.sleeve,
            universe_definition=exp.universe_definition,
            parameters=exp.parameters,
            preset=exp.preset,
            hypothesis=exp.hypothesis,
            null_hypothesis=exp.null_hypothesis,
            success_criteria=exp.success_criteria,
            failure_criteria=exp.failure_criteria,
        )
    )
    if not validation.can_run:
        raise ValueError("experiment validation failed — cannot run")

    job = create_job(experiment_id, experiment_type=exp.experiment_type)
    _EXECUTOR.submit(_run_job, job.job_id, experiment_id)
    return ExperimentLaunchResponse(
        job_id=job.job_id,
        experiment_id=experiment_id,
        status="pending",
        message="Experiment job queued.",
    )


def _run_job(job_id: str, experiment_id: str) -> None:
    exp = get_experiment(experiment_id)
    if not exp:
        fail_job(job_id, "validating", "experiment not found")
        return

    last_success: str | None = None
    prior = get_job(job_id)
    if prior and prior.last_success_run_id:
        last_success = prior.last_success_run_id

    try:
        mark_stage(job_id, "validating", "running", "Checking configuration")
        validation = validate_experiment(
            ExperimentValidateRequest(
                experiment_type=exp.experiment_type,
                sleeve=exp.sleeve,
                universe_definition=exp.universe_definition,
                parameters=exp.parameters,
                preset=exp.preset,
                hypothesis=exp.hypothesis,
                null_hypothesis=exp.null_hypothesis,
                success_criteria=exp.success_criteria,
                failure_criteria=exp.failure_criteria,
            )
        )
        if not validation.can_run:
            fail_job(job_id, "validating", "Validation failed", preserve_last_success=True)
            return
        complete_stage(job_id, "validating", "Configuration valid")

        merged = validation.merged_parameters
        mark_stage(job_id, "resolving_universe", "running")
        symbols, source, _ = resolve_universe(
            exp.universe_definition, sleeve=exp.sleeve, parameters=merged
        )
        complete_stage(job_id, "resolving_universe", f"{len(symbols)} symbols from {source}")

        mark_stage(job_id, "loading_prices", "running")
        complete_stage(job_id, "loading_prices", "Price panel deferred to engine")

        if exp.experiment_type == "scan_evaluation":
            run_id = _run_scan_evaluation(exp, symbols, merged, job_id)
            complete_stage(job_id, "evaluating_reliability", "Reliability evaluated")
        else:
            mark_stage(job_id, "calculating_features", "running")
            complete_stage(job_id, "calculating_features", "Features calculated by engine")

            mark_stage(job_id, "running_analysis", "running")
            run_id = _dispatch_experiment(exp, symbols, merged, job_id)
            complete_stage(job_id, "running_analysis", f"Analysis complete: {run_id}")

            mark_stage(job_id, "calculating_outcomes", "running")
            complete_stage(job_id, "calculating_outcomes", "Outcomes calculated")

            mark_stage(job_id, "evaluating_reliability", "running")
            complete_stage(job_id, "evaluating_reliability", "Reliability evaluated")

        mark_stage(job_id, "persisting_result", "running")
        if run_id:
            link_run_to_experiment(run_id, experiment_id, idea_id=exp.idea_id)
            last_success = run_id
        complete_stage(job_id, "persisting_result", "Result indexed")

        if exp.idea_id:
            try:
                update_idea(exp.idea_id, ResearchIdeaUpdate(status="running"))
            except Exception:
                pass

        update_job(
            job_id,
            status="completed",
            current_stage="complete",
            run_id=run_id,
            last_success_run_id=last_success,
            stage_update=("complete", "completed", "Experiment complete"),
        )
    except Exception as exc:
        logger.exception("experiment job %s failed", job_id)
        fail_job(job_id, "running_analysis", str(exc), preserve_last_success=True)
        if last_success:
            update_job(job_id, last_success_run_id=last_success)


def _dispatch_experiment(
    exp: Any,
    symbols: list[str],
    merged: dict[str, Any],
    job_id: str,
) -> str | None:
    exp_type = exp.experiment_type
    if exp_type == "walk_forward":
        return _run_walk_forward(exp, symbols, merged)
    if exp_type == "pairs_discovery":
        return _run_pairs(exp, symbols, merged)
    if exp_type == "factor_validation":
        return _run_factor_validation(exp, symbols, merged)
    if exp_type == "prediction_calibration":
        return _run_prediction_calibration(exp, merged)
    if exp_type == "similar_signal":
        return _run_similar_signal(exp, symbols, merged)
    if exp_type == "portfolio_policy":
        return _run_portfolio_policy(exp, symbols, merged)
    if exp_type == "scan_evaluation":
        raise ValueError("scan_evaluation must use _run_scan_evaluation from _run_job")
    if exp_type == "factor_discovery":
        return _run_factor_discovery(exp, merged, job_id)
    raise ValueError(f"unsupported experiment type: {exp_type}")


_SCAN_RUNNER_STAGE_MAP: dict[str, str] = {
    "preparing_universe": "preparing_universe",
    "replaying_scans": "replaying_scans",
    "comparing_algorithms": "replaying_scans",
    "loading_historical_data": "loading_prices",
    "calculating_forward_outcomes": "calculating_forward_outcomes",
}


def _run_scan_evaluation(exp: Any, symbols: list[str], merged: dict[str, Any], job_id: str) -> str:
    from services.scan_evaluation_experiment_runner import ScanEvaluationExperimentRunner

    bucket = str(merged.get("bucket") or exp.sleeve or "penny")
    merged = {**merged, "bucket": bucket, "sleeve": bucket}

    def on_stage(stage: str, status: str, message: str) -> None:
        mapped = _SCAN_RUNNER_STAGE_MAP.get(stage, stage)
        if status == "running":
            mark_stage(job_id, mapped, "running", message)
        elif status == "completed":
            complete_stage(job_id, mapped, message)

    mark_stage(job_id, "preparing_universe", "running", "Preparing evaluation universe")
    payload = ScanEvaluationExperimentRunner().run(bucket=bucket, merged=merged, on_stage=on_stage)
    complete_stage(job_id, "preparing_universe", "Universe prepared")

    mark_stage(job_id, "generating_charts", "running", "Building chart artifacts")
    complete_stage(job_id, "generating_charts", "Charts generated")

    run_id = str(payload["run_id"])
    now = _utcnow()
    from data.db_engine import get_engine
    from engines.quant_models import BacktestRun
    from sqlalchemy.orm import Session

    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(BacktestRun, run_id)
        if not existing:
            row = BacktestRun(
                run_id=run_id,
                run_type="scan_evaluation",
                config_json=json.dumps(
                    {
                        "experiment_id": exp.id,
                        "parameters": merged,
                        "sleeve": bucket,
                        "symbols_resolved": len(symbols),
                    }
                ),
                metrics_json=json.dumps(payload),
                started_at=now,
                finished_at=now,
            )
            session.add(row)
            session.commit()

    notify_run_persisted(run_id, store="backtest_runs")
    return run_id


def _run_factor_discovery(exp: Any, merged: dict[str, Any], job_id: str) -> str:
    from models.schemas_factor_discovery import DiscoveryPeriodSplit
    from engines.factor.discovery.validation_models import FactorValidationConfig
    from services.factor_discovery.experiment_runner import FactorDiscoveryExperimentRunner, FactorDiscoveryRunRequest

    period = DiscoveryPeriodSplit.model_validate(merged["period_split"])
    vconfig = FactorValidationConfig.model_validate(merged.get("validation_config") or {})
    runner = FactorDiscoveryExperimentRunner()

    def on_stage(stage: str, status: str, message: str) -> None:
        if status == "running":
            mark_stage(job_id, stage, "running", message or stage)
        elif status == "completed":
            complete_stage(job_id, stage, message or stage)

    result = runner.run(
        FactorDiscoveryRunRequest(
            experiment_id=exp.id,
            job_id=job_id,
            factor_id=str(merged["factor_id"]),
            factor_version=str(merged["factor_version"]),
            research_family_id=str(merged["research_family_id"]),
            period_split=period,
            validation_config=vconfig,
            created_by=str(merged.get("created_by") or "system"),
            idempotency_key=merged.get("idempotency_key"),
            declared_family_size=merged.get("declared_family_size"),
            validation_config_family_id=str(merged.get("validation_config_family_id") or "default_v1"),
        ),
        on_stage=on_stage,
    )
    return str(result["run_id"])


def _run_walk_forward(exp: Any, symbols: list[str], merged: dict[str, Any]) -> str:
    from services.walk_forward_research_service import WalkForwardConfig, run_walk_forward_research

    cfg = WalkForwardConfig(
        sleeve=exp.sleeve or "penny",
        start_date=str(merged["start_date"]),
        end_date=str(merged["end_date"]),
        rebalance_frequency=str(merged.get("rebalance_frequency") or "monthly"),
        forward_horizons=list(merged.get("forward_horizons") or [20]),
        max_symbols=int(merged.get("max_symbols") or len(symbols) or 30),
        persist_snapshots=not DEMO_MODE and bool(merged.get("persist_snapshots", False)),
    )
    result = run_walk_forward_research(cfg)
    notify_run_persisted(result.run_id, store="backtest_runs")
    return result.run_id


def _run_pairs(exp: Any, symbols: list[str], merged: dict[str, Any]) -> str:
    from services.pairs_research_service import run_pairs_research
    from services.pairs_research_store import persist_pairs_run

    syms = symbols if len(symbols) >= 2 else merged.get("symbols") or []
    if len(syms) < 2:
        raise ValueError("pairs discovery requires at least 2 symbols")
    result = run_pairs_research(
        syms,
        lookback_period=str(merged.get("lookback_period") or "1y"),
        zscore_window=int(merged.get("zscore_window") or 60),
        max_pairs=int(merged.get("pairs_max_pairs") or merged.get("max_pairs") or 50),
        p_value_threshold=merged.get("p_value_threshold"),
    )
    run_id = persist_pairs_run(result)
    notify_run_persisted(run_id, store="pairs_research_runs")
    return run_id


def _run_factor_validation(exp: Any, symbols: list[str], merged: dict[str, Any]) -> str:
    from engines.factors.performance import get_factor_performance
    from engines.weighting.ic_panel import run_ic_panel

    sleeve = exp.sleeve or "penny"
    factors = merged.get("factors") or merged.get("factor_ids") or []
    if isinstance(factors, str):
        factors = [factors]
    horizons = merged.get("horizons") or merged.get("forward_horizons")

    if merged.get("force_ic_refresh"):
        run_ic_panel(symbols=symbols or None, sleeves=[sleeve], horizons=horizons)

    perf = get_factor_performance(sleeve=sleeve, factor_id=None)
    factor_rows = []
    for f in perf.get("factors") or []:
        fid = f.get("factor_id")
        if factors and fid not in factors:
            continue
        factor_rows.append(f)

    as_of = perf.get("as_of_date") or _utcnow().strftime("%Y-%m-%d")
    run_id = f"factor_validation:{sleeve}:{as_of}:{uuid.uuid4().hex[:8]}"
    summary = {
        "run_id": run_id,
        "experiment_type": "factor_validation",
        "sleeve": sleeve,
        "as_of_date": as_of,
        "factors": factor_rows,
        "by_horizon": perf.get("by_horizon"),
        "by_regime": perf.get("by_regime"),
        "symbols_used": symbols[:20],
        "preset": exp.preset,
        "major_evidence_eligible": preset_allows_major_evidence(exp.preset),
    }
    _persist_synthetic_run(
        run_id,
        run_type="factor_ic_panel",
        name=exp.name,
        sleeve=sleeve,
        universe=symbols,
        parameters=merged,
        summary=summary,
        experiment_id=exp.id,
    )
    notify_run_persisted(run_id, store="factor_ic_history")
    return run_id


def _run_prediction_calibration(exp: Any, merged: dict[str, Any]) -> str:
    if not bool(SCORE_ENGINE_V2_ENABLED):
        raise ValueError("SCORE_ENGINE_V2_ENABLED is false")
    from engines.prediction.snapshots import resolve_prediction_outcomes
    from engines.weighting.forward_returns import build_forward_labels

    if merged.get("build_forward_labels", True):
        build_forward_labels()
    resolved = resolve_prediction_outcomes(min_age_days=int(merged.get("min_age_days") or 5))
    run_id = f"prediction_calibration:{uuid.uuid4().hex[:12]}"
    summary = {
        "run_id": run_id,
        "resolved": resolved.get("resolved", 0),
        "skipped": resolved.get("skipped", 0),
        "horizons": resolved.get("horizons", []),
        "sleeve": exp.sleeve,
        "filters": {
            k: merged.get(k)
            for k in ("symbol", "recommendation", "horizon", "resolution_state", "regime")
            if merged.get(k) is not None
        },
    }
    _persist_synthetic_run(
        run_id,
        run_type="prediction_outcomes",
        name=exp.name,
        sleeve=exp.sleeve,
        universe=[],
        parameters=merged,
        summary=summary,
        experiment_id=exp.id,
    )
    notify_run_persisted(run_id, store="prediction_snapshots")
    return run_id


def _run_similar_signal(exp: Any, symbols: list[str], merged: dict[str, Any]) -> str:
    from engines.backtest.similar_signal import run_similar_signal_backtest

    symbol = str(merged.get("symbol") or (symbols[0] if symbols else "")).upper()
    if not symbol:
        raise ValueError("symbol required for similar-signal replay")
    sleeve = exp.sleeve or "penny"
    result = run_similar_signal_backtest(
        symbol=symbol,
        sleeve=sleeve,
        current_factors=merged.get("current_factors") or {},
        forward_days=int(merged.get("forward_days") or 60),
    )
    run_id = f"similar_signal:{symbol}:{uuid.uuid4().hex[:8]}"
    _persist_synthetic_run(
        run_id,
        run_type="similar_signal",
        name=exp.name,
        sleeve=sleeve,
        universe=[symbol],
        parameters={**merged, "symbol": symbol},
        summary=result,
        experiment_id=exp.id,
    )
    notify_run_persisted(run_id, store="backtest_runs")
    return run_id


def _run_portfolio_policy(exp: Any, symbols: list[str], merged: dict[str, Any]) -> str:
    from models.schemas import PortfolioPolicyBacktestRequest
    from services.institutional_backtest_service import run_portfolio_backtest

    syms = symbols if len(symbols) >= 2 else []
    if len(syms) < 2:
        raise ValueError("portfolio policy backtest requires at least 2 symbols")
    body = PortfolioPolicyBacktestRequest(
        symbols=syms,
        policy=merged.get("policy") or "equal_weight",
        rebalance=merged.get("rebalance") or "monthly",
        top_n=int(merged.get("top_n") or 5),
        lookback_period=str(merged.get("lookback_period") or "1y"),
        sleeve=exp.sleeve or "penny",
        fee_bps=float(merged.get("cost_assumption_bps") or merged.get("fee_bps") or 5),
        slip_bps=float(merged.get("slippage_bps") or merged.get("slip_bps") or 5),
        institutional=bool(merged.get("institutional_backtest", True)),
    )
    resp = run_portfolio_backtest(body)
    run_id = resp.run_id or f"portfolio_policy:{uuid.uuid4().hex[:12]}"
    if not resp.run_id:
        _persist_synthetic_run(
            run_id,
            run_type="portfolio_policy",
            name=exp.name,
            sleeve=exp.sleeve,
            universe=syms,
            parameters=merged,
            summary=resp.model_dump(),
            experiment_id=exp.id,
        )
        notify_run_persisted(run_id, store="backtest_runs")
    else:
        notify_run_persisted(run_id, store="backtest_runs")
    return run_id


def _persist_synthetic_run(
    run_id: str,
    *,
    run_type: str,
    name: str,
    sleeve: str | None,
    universe: list[str],
    parameters: dict[str, Any],
    summary: dict[str, Any],
    experiment_id: str,
) -> None:
    """Store thin backtest_runs row for types without native persistence."""
    from data.db_engine import get_engine
    from engines.quant_models import BacktestRun
    from sqlalchemy.orm import Session

    now = _utcnow()
    engine = get_engine()
    with Session(engine) as session:
        existing = session.get(BacktestRun, run_id)
        if existing:
            return
        row = BacktestRun(
            run_id=run_id,
            run_type=run_type,
            config_json=json.dumps({"experiment_id": experiment_id, "parameters": parameters, "sleeve": sleeve}),
            metrics_json=json.dumps(summary),
            started_at=now,
            finished_at=now,
        )
        session.add(row)
        session.commit()
