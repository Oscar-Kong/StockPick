"""Quant v2 API — parallel to v1 analyze; does not change v1 response shape."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from buckets import DEFAULT_BUCKET
from config import DYNAMIC_WEIGHTS_ENABLED, SCORE_ENGINE_V2_ENABLED
from models.schemas import Bucket, PortfolioPolicyBacktestRequest, PortfolioPolicyBacktestResponse
from config import AI_REPORT_SCHEMA, BACKTEST_INSTITUTIONAL, POSITION_SIZING_V2, TRADE_FEEDBACK_ENABLED
from models.schemas_v2 import MarketRegimeV2, PositionSizingV2, QuantLabEvidenceResponse, SleeveWeightsV2, UnifiedRiskV2, V2ScoreResponse
from services.institutional_backtest_service import run_portfolio_backtest
from services.quant_risk_sizing_service import build_position_sizing, build_unified_risk
from services.research_report_v2 import build_research_report_v2, get_cached_report_v2
from engines.weighting.regime_classifier import classify_spy
from engines.weighting.weight_store import WeightStore
from services.quant_jobs import run_daily_quant_jobs
from services.quant_v2_service import build_v2_score

router = APIRouter(prefix="/api/v2", tags=["quant-v2"])


@router.get("/score/{symbol}", response_model=V2ScoreResponse)
def get_v2_score(
    symbol: str,
    sleeve: Bucket | None = Query(None, description="penny | medium | compounder"),
    validate_parity: bool = Query(True, description="Compare to legacy analyze score"),
    x_strategy_version: str | None = Header(None, alias="X-Strategy-Version"),
    x_factor_model_version: str | None = Header(None, alias="X-Factor-Model-Version"),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from services.version_pin import enforce_client_versions

    enforce_client_versions(
        strategy_version=x_strategy_version,
        factor_model_version=x_factor_model_version,
    )
    sleeve_val = sleeve.value if sleeve else DEFAULT_BUCKET
    result = build_v2_score(symbol, sleeve_val, validate_parity=validate_parity)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/regime", response_model=MarketRegimeV2)
def get_market_regime(refresh: bool = Query(False)):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    if refresh:
        result = classify_spy()
        if result:
            WeightStore.persist_regime(result)
    else:
        result = classify_spy()
    if not result:
        raise HTTPException(status_code=503, detail="Could not classify market regime")
    return MarketRegimeV2(
        regime=result.regime,
        as_of_date=result.features.as_of_date,
        features=result.features_json,
    )


@router.get("/weights/{sleeve}", response_model=SleeveWeightsV2)
def get_sleeve_weights(
    sleeve: Bucket,
    regime: str | None = Query(None, description="Regime key; default = current"),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    sleeve_val = sleeve.value
    regime_val = regime or WeightStore.current_regime()
    weights = WeightStore.load(sleeve_val, regime_val)
    by_regime = WeightStore.list_active_weights(sleeve_val) if DYNAMIC_WEIGHTS_ENABLED else None
    return SleeveWeightsV2(
        sleeve=sleeve_val,
        regime=regime_val,
        dynamic_enabled=bool(DYNAMIC_WEIGHTS_ENABLED),
        weights=weights,
        weights_by_regime=by_regime,
    )


@router.post("/jobs/ic-panel")
def trigger_ic_panel():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.weighting.ic_panel import run_ic_panel

    return run_ic_panel()


@router.post("/jobs/rebalance")
def trigger_rebalance(force: bool = Query(True)):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    return run_daily_quant_jobs(force_rebalance=force)


@router.get("/hard-filters/{sleeve}")
def list_hard_filters(sleeve: Bucket):
    from engines.filters.hard_filters import HARD_FILTER_TABLE

    rules = [
        {
            "filter_id": r.filter_id,
            "action": r.action,
            "description": r.description,
        }
        for r in HARD_FILTER_TABLE
        if r.sleeve == sleeve.value
    ]
    return {"sleeve": sleeve.value, "rules": rules}


@router.post("/backtest/portfolio", response_model=PortfolioPolicyBacktestResponse)
def institutional_portfolio_backtest(body: PortfolioPolicyBacktestRequest):
    if not BACKTEST_INSTITUTIONAL and not body.institutional:
        raise HTTPException(
            status_code=503,
            detail="Set BACKTEST_INSTITUTIONAL=true or pass institutional=true",
        )
    body = body.model_copy(update={"institutional": True})
    try:
        return run_portfolio_backtest(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/risk/{symbol}", response_model=UnifiedRiskV2)
def get_unified_risk(
    symbol: str,
    sleeve: Bucket | None = Query(None),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    sleeve_val = sleeve.value if sleeve else DEFAULT_BUCKET
    result = build_unified_risk(symbol, sleeve_val)
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/sizing/{symbol}", response_model=PositionSizingV2)
def get_position_sizing(
    symbol: str,
    sleeve: Bucket | None = Query(None),
    portfolio_exposure: float | None = Query(None, ge=0, le=1),
    active_positions: int | None = Query(None, ge=0, le=100),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    if not POSITION_SIZING_V2:
        raise HTTPException(status_code=503, detail="POSITION_SIZING_V2 is false")
    sleeve_val = sleeve.value if sleeve else DEFAULT_BUCKET
    result = build_position_sizing(
        symbol,
        sleeve_val,
        portfolio_exposure=portfolio_exposure,
        active_positions=active_positions,
    )
    if result is None:
        raise HTTPException(status_code=503, detail="Sizing unavailable")
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/report/{symbol}")
def get_report_v2(
    symbol: str,
    sleeve: Bucket | None = Query(None),
    refresh: bool = Query(False),
):
    if AI_REPORT_SCHEMA != "v2":
        raise HTTPException(status_code=503, detail="Set AI_REPORT_SCHEMA=v2")
    sleeve_val = sleeve.value if sleeve else None
    sym = symbol.upper()
    if not refresh:
        cached = get_cached_report_v2(sym, sleeve_val or DEFAULT_BUCKET)
        if cached:
            return cached
    data = build_research_report_v2(sym, sleeve_val)
    if data.get("error"):
        raise HTTPException(status_code=404, detail=data["error"])
    return data


@router.get("/feedback/summary")
def feedback_summary():
    if not TRADE_FEEDBACK_ENABLED:
        raise HTTPException(status_code=503, detail="TRADE_FEEDBACK_ENABLED is false")
    from services.trade_feedback_service import feedback_summary as _summary

    return _summary()


@router.get("/feedback/trades/{trade_id}")
def trade_feedback(trade_id: int):
    if not TRADE_FEEDBACK_ENABLED:
        raise HTTPException(status_code=503, detail="TRADE_FEEDBACK_ENABLED is false")
    from services.trade_feedback_service import get_trade_feedback

    return get_trade_feedback(trade_id)


@router.get("/factors/performance")
def get_factors_performance(
    sleeve: Bucket | None = Query(None),
    factor_id: str | None = Query(None),
    horizon_days: int | None = Query(None, ge=1, le=365),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.factors.performance import get_factor_performance

    sleeve_val = sleeve.value if sleeve else None
    return get_factor_performance(sleeve=sleeve_val, factor_id=factor_id, horizon_days=horizon_days)


@router.get("/factors/ic")
def get_factors_ic(
    sleeve: Bucket | None = Query(None),
    factor_id: str | None = Query(None),
    horizon_days: int | None = Query(None, ge=1, le=365),
):
    """Alias for /factors/performance."""
    return get_factors_performance(sleeve=sleeve, factor_id=factor_id, horizon_days=horizon_days)


@router.get("/predictions")
def list_predictions(
    symbol: str | None = Query(None),
    source: str | None = Query(None),
    sleeve: Bucket | None = Query(None),
    from_date: str | None = Query(None),
    to_date: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.prediction.snapshots import list_recent_snapshots

    return {
        "predictions": list_recent_snapshots(
            limit=limit,
            symbol=symbol,
            source=source,
            sleeve=sleeve.value if sleeve else None,
            from_date=from_date,
            to_date=to_date,
        )
    }


@router.post("/jobs/forward-labels")
def trigger_forward_labels():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.labels.forward_returns import build_forward_labels

    return build_forward_labels()


@router.post("/jobs/outcome-weights")
def trigger_outcome_weights():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.feedback.outcome_weights import run_outcome_weight_feedback

    return run_outcome_weight_feedback()


@router.post("/jobs/resolve-outcomes")
def trigger_outcome_resolution():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.prediction.snapshots import resolve_prediction_outcomes

    return resolve_prediction_outcomes()


@router.get("/valuation/{symbol}")
def get_valuation(symbol: str):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from data.reconciler import DataReconciler
    from engines.valuation.engine import evaluate_valuation

    sym = symbol.upper()
    info, fundamentals, _ = DataReconciler().get_canonical_fundamentals(sym)
    if not info:
        raise HTTPException(status_code=404, detail=f"No data for {sym}")
    return evaluate_valuation(info, fundamentals).to_dict()


@router.get("/similar-signal/{symbol}")
def get_similar_signal(
    symbol: str,
    sleeve: Bucket | None = Query(None),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from engines.backtest.similar_signal import run_similar_signal_backtest

    sleeve_val = sleeve.value if sleeve else DEFAULT_BUCKET
    score = build_v2_score(symbol, sleeve_val, validate_parity=False, persist_snapshot=False)
    if isinstance(score, dict) and score.get("error"):
        raise HTTPException(status_code=404, detail=score["error"])
    factors = [f.model_dump() for f in score.factors]
    return run_similar_signal_backtest(
        symbol=symbol.upper(),
        sleeve=sleeve_val,
        current_factors=factors,
        market_regime=score.market_regime,
    )


@router.get("/agents/{symbol}")
def get_agent_pipeline(
    symbol: str,
    sleeve: Bucket | None = Query(None),
):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    result = build_v2_score(
        symbol,
        sleeve.value if sleeve else DEFAULT_BUCKET,
        validate_parity=False,
        persist_snapshot=False,
    )
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    if not result.agents:
        raise HTTPException(status_code=503, detail="Agent pipeline unavailable")
    return result.agents


@router.post("/jobs/pit-fundamentals")
def trigger_pit_fundamentals():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from data.pit_fmp_ingest import build_pit_panel

    return build_pit_panel()


@router.get("/admin/round2-stats")
def round2_stats():
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from services.round2_admin import round2_ops_stats

    return round2_ops_stats()


@router.get("/factors/admin")
def factors_admin(sleeve: Bucket | None = Query(None)):
    if not SCORE_ENGINE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="SCORE_ENGINE_V2_ENABLED is false")
    from services.trade_feedback_service import factor_admin_view

    sleeve_val = sleeve.value if sleeve else None
    return factor_admin_view(sleeve_val)


@router.get("/quant-lab/evidence", response_model=QuantLabEvidenceResponse)
def get_quant_lab_evidence(sleeve: Bucket = Query(Bucket.penny)):
    """Read-only latest evidence summaries for Quant Lab overview cards."""
    from services.quant_lab_summary_service import get_quant_lab_evidence as _evidence

    return _evidence(sleeve.value)


@router.get("/version")
def get_pinned_version():
    from services.version_pin import pinned_versions

    return pinned_versions()


@router.get("/audit")
def list_audit(
    limit: int = Query(50, ge=1, le=500),
    event_type: str | None = Query(None),
    symbol: str | None = Query(None),
):
    from engines.audit.logger import list_audit_logs

    return {"events": list_audit_logs(limit=limit, event_type=event_type, symbol=symbol)}


@router.get("/jobs/queue")
def list_jobs(limit: int = Query(20, ge=1, le=100)):
    from engines.jobs.queue import effective_backend, list_queued_jobs

    return {"backend": effective_backend(), "jobs": list_queued_jobs(limit=limit)}


@router.post("/jobs/enqueue/{job_name}")
def enqueue_background_job(job_name: str, force_rebalance: bool = Query(False)):
    from engines.jobs.queue import dispatch_job

    payload = {"force_rebalance": force_rebalance} if job_name == "quant_daily_jobs" else {}
    try:
        return dispatch_job(job_name, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
