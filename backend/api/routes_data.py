"""Data quality, strategy version, and scheduler status API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from config import QUANDL_API_KEY
from data.historical_store import HistoricalStore
from data.quandl_client import QuandlClient
from data.reconciler import DataReconciler
from data.strategy_registry import StrategyRegistry
from core.sleeve import normalize_sleeve
from models.schemas import (
    DataQualityResponse,
    JobLogEntry,
    OpenBBRiskResponse,
    ReconcileResponse,
    SchedulerStatusResponse,
    StrategyVersionResponse,
)
from services.scheduler import refresh_fundamentals, refresh_universe_quotes, run_daily_pipeline
from utils.demo_guard import require_non_demo_mode

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/openbb/risk/{symbol}", response_model=OpenBBRiskResponse)
def openbb_risk(symbol: str):
    """SEC / insider governance snapshot (requires OPENBB_ENABLED=true)."""
    from data.openbb_client import get_risk_snapshot, is_available

    sym = symbol.upper()
    if not is_available():
        return OpenBBRiskResponse(
            symbol=sym,
            governance_score=0.0,
            warnings=["OpenBB not enabled — set OPENBB_ENABLED=true and install requirements-openbb.txt"],
            openbb_available=False,
        )
    snap = get_risk_snapshot(sym, allow_fetch=True, use_cache=True)
    return OpenBBRiskResponse(
        symbol=sym,
        governance_score=snap.governance_score,
        warnings=snap.warnings,
        flags=snap.flags,
        insider_sell_ratio=snap.insider_sell_ratio,
        recent_filings=snap.recent_filings[:5],
        openbb_available=True,
    )


@router.get("/reconcile/{symbol}", response_model=ReconcileResponse)
def reconcile_symbol(symbol: str):
    result = DataReconciler().reconcile(symbol.upper())
    return ReconcileResponse(**result.to_dict())


@router.get("/quality/{symbol}", response_model=DataQualityResponse)
def get_data_quality(symbol: str):
    store = HistoricalStore()
    flags = store.get_quality_flags(symbol.upper())
    rec = DataReconciler().reconcile(symbol.upper())
    return DataQualityResponse(
        symbol=symbol.upper(),
        quality_score=rec.quality_score,
        flags=flags + [{"flag_type": "reconcile", "message": f, "created_at": None} for f in rec.flags],
        reconcile=rec.to_dict(),
    )


@router.get("/strategy/{bucket}", response_model=StrategyVersionResponse)
def get_strategy_version(bucket: str):
    bucket = normalize_sleeve(bucket)
    if bucket not in ("penny", "compounder"):
        raise HTTPException(status_code=400, detail="Invalid bucket")
    cfg = StrategyRegistry().get_active(bucket)
    return StrategyVersionResponse(
        version_id=cfg.version_id,
        bucket=bucket,
        config=cfg.config,
    )


@router.get("/strategy", response_model=list[StrategyVersionResponse])
def list_strategies(bucket: str | None = None):
    rows = StrategyRegistry().list_versions(bucket)
    return [
        StrategyVersionResponse(version_id=r["version_id"], bucket=r["bucket"], config=r["config"])
        for r in rows
    ]


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
def scheduler_status():
    store = HistoricalStore()
    logs = store.get_recent_job_logs(10)
    return SchedulerStatusResponse(
        enabled=True,
        recent_jobs=[JobLogEntry(**j) for j in logs],
        quandl_configured=bool(QUANDL_API_KEY),
    )


@router.post("/scheduler/run")
def trigger_daily_pipeline():
    require_non_demo_mode()
    result = run_daily_pipeline()
    return result


@router.post("/scheduler/refresh-quotes")
def trigger_quote_refresh():
    require_non_demo_mode()
    return refresh_universe_quotes()


@router.post("/scheduler/refresh-fundamentals")
def trigger_fundamentals_refresh():
    require_non_demo_mode()
    return refresh_fundamentals()


@router.post("/scheduler/refresh-listing-master")
def trigger_listing_master_refresh(force: bool = Query(False)):
    """Refresh Nasdaq Trader symbol directories into the listing master cache."""
    require_non_demo_mode()
    from data.listing_master import refresh_listing_master

    return refresh_listing_master(force=force)


@router.get("/universe/listing-master")
def get_listing_master_status():
    """Inspect cached listing master snapshot metadata (not full symbol list)."""
    from data.listing_master import CACHE_KEY_SNAPSHOT, get_listing_revision
    from data.cache import Cache

    snap = Cache().get(CACHE_KEY_SNAPSHOT)
    if not snap:
        return {"status": "missing", "revision": get_listing_revision()}
    return {
        "status": "cached",
        "revision": get_listing_revision(),
        "updated_at": snap.get("updated_at"),
        "source": snap.get("source"),
        "record_count": snap.get("record_count"),
    }


@router.post("/refresh")
def data_refresh(scope: str = Query("home", description="home | portfolio | prices | penny_scan | all"), force: bool = False):
    require_non_demo_mode()
    from services.refresh_orchestrator import refresh_if_stale

    try:
        return refresh_if_stale(scope, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
