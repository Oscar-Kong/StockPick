"""Registered background job handlers for the job queue."""
from __future__ import annotations

from typing import Any, Callable

JobHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _quant_daily(payload: dict[str, Any]) -> dict[str, Any]:
    from services.quant_jobs import run_daily_quant_jobs

    return run_daily_quant_jobs(force_rebalance=bool(payload.get("force_rebalance")))


def _daily_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    from services.scheduler import run_daily_pipeline

    return run_daily_pipeline()


def _daily_portfolio_decision(payload: dict[str, Any]) -> dict[str, Any]:
    from services.portfolio_jobs import run_scheduled_portfolio_decision

    return run_scheduled_portfolio_decision()


def _market_data_price_refresh(payload: dict[str, Any]) -> dict[str, Any]:
    from services.portfolio_jobs import run_market_data_price_refresh

    return run_market_data_price_refresh()


def _penny_scan_refresh(payload: dict[str, Any]) -> dict[str, Any]:
    from services.portfolio_jobs import run_scheduled_penny_scan_refresh

    return run_scheduled_penny_scan_refresh()


def _home_refresh(payload: dict[str, Any]) -> dict[str, Any]:
    from services.refresh_orchestrator import refresh_home_dashboard

    return refresh_home_dashboard(force=bool(payload.get("force")))


JOB_HANDLERS: dict[str, JobHandler] = {
    "quant_daily_jobs": _quant_daily,
    "daily_pipeline": _daily_pipeline,
    "daily_portfolio_decision": _daily_portfolio_decision,
    "market_data_price_refresh": _market_data_price_refresh,
    "penny_scan_refresh": _penny_scan_refresh,
    "home_refresh": _home_refresh,
}


def run_job(job_name: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = JOB_HANDLERS.get(job_name)
    if not handler:
        raise ValueError(f"Unknown job: {job_name}")
    return handler(payload or {})
