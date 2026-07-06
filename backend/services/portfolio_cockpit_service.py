"""Portfolio Today cockpit — unified read surface for daily decisions."""
from __future__ import annotations

from models.schemas import DailyDashboardResponse, PortfolioSummaryResponse
from services.home_dashboard_service import build_daily_dashboard
from services.portfolio_summary_service import build_portfolio_summary
from services.refresh_orchestrator import (
    get_active_home_job_id,
    is_home_refresh_running,
    portfolio_refresh,
    try_begin_auto_refresh,
)


def get_today_view(*, include_freshness: bool = True, skip_auto_refresh: bool = False) -> DailyDashboardResponse:
    # Auto-refresh gating lives in routes_home._attach_auto_refresh (skip_auto_refresh query).
    _ = skip_auto_refresh
    return build_daily_dashboard(include_freshness=include_freshness)


def get_summary() -> PortfolioSummaryResponse:
    payload = build_portfolio_summary()
    return PortfolioSummaryResponse.model_validate(payload)


def begin_refresh_if_needed(*, force: bool = False):
    if force:
        return portfolio_refresh.start_home_async(force=True)
    return try_begin_auto_refresh()


def refresh_state() -> tuple[bool, str | None]:
    return is_home_refresh_running(), get_active_home_job_id()
