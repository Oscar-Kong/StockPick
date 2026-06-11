"""Home dashboard — daily decision first with stale-while-revalidate."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from models.schemas import (
    DailyDashboardResponse,
    HomeRefreshResponse,
    HomeRefreshStatusResponse,
)
from services.home_dashboard_service import build_daily_dashboard
from services.refresh_orchestrator import (
    auto_refresh_allowed,
    get_active_home_job_id,
    get_refresh_job,
    is_home_refresh_running,
    mark_auto_refresh_started,
    start_home_refresh_async,
)

router = APIRouter(prefix="/home", tags=["home"])


def _attach_auto_refresh(dashboard: DailyDashboardResponse) -> DailyDashboardResponse:
    freshness = dashboard.freshness
    if not freshness:
        return dashboard

    active_job = get_active_home_job_id()
    if active_job:
        freshness.refresh_job_id = active_job

    if is_home_refresh_running():
        freshness.overall_status = "updating"
        freshness.refresh_in_progress = True
        freshness.refresh_recommended = False
        return dashboard

    if not freshness.refresh_recommended:
        return dashboard

    if not auto_refresh_allowed():
        return dashboard

    job_id = start_home_refresh_async(force=False)
    if job_id:
        mark_auto_refresh_started()
        freshness.refresh_job_id = job_id
        freshness.overall_status = "updating"
        freshness.refresh_in_progress = True
        freshness.refresh_recommended = False
    return dashboard


@router.get("/daily-dashboard", response_model=DailyDashboardResponse)
def daily_dashboard(skip_auto_refresh: bool = Query(False, description="Poll without starting another background refresh")):
    dashboard = build_daily_dashboard(include_freshness=True)
    if skip_auto_refresh:
        return dashboard
    return _attach_auto_refresh(dashboard)


@router.post("/refresh", response_model=HomeRefreshResponse)
def refresh_home(force: bool = Query(False, description="Bypass TTL guards")):
    active = get_active_home_job_id()
    if is_home_refresh_running() and not force:
        return HomeRefreshResponse(
            job_id=active or "",
            status="running",
            message="Home refresh already in progress",
        )

    job_id = start_home_refresh_async(force=force)
    if not job_id:
        return HomeRefreshResponse(
            job_id=active or "",
            status="running",
            message="Home refresh already in progress",
        )
    return HomeRefreshResponse(job_id=job_id, status="running", message="Background refresh started")


@router.get("/refresh-status/{job_id}", response_model=HomeRefreshStatusResponse)
def refresh_status(job_id: str):
    if not job_id:
        status = "running" if is_home_refresh_running() else "failed"
        return HomeRefreshStatusResponse(job_id=job_id, status=status)
    job = get_refresh_job(job_id)
    if not job:
        if is_home_refresh_running():
            return HomeRefreshStatusResponse(job_id=job_id, status="running")
        raise HTTPException(status_code=404, detail="Refresh job not found")
    return HomeRefreshStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        started_at=job.get("started_at"),
        finished_at=job.get("finished_at"),
        error=job.get("error"),
        result=job.get("result"),
    )
