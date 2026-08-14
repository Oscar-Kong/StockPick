"""Portfolio Today cockpit — unified read surface for daily decisions."""
from __future__ import annotations

from models.schemas import DailyDashboardResponse, PortfolioSummaryResponse
from services.home_dashboard_service import build_daily_dashboard
from services.portfolio_summary_service import build_portfolio_summary


def get_today_view(*, include_freshness: bool = True) -> DailyDashboardResponse:
    return build_daily_dashboard(include_freshness=include_freshness)


def get_summary() -> PortfolioSummaryResponse:
    payload = build_portfolio_summary()
    return PortfolioSummaryResponse.model_validate(payload)
