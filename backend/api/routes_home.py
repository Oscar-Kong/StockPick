"""Home dashboard — read-only daily cockpit."""
from __future__ import annotations

from fastapi import APIRouter

from models.schemas import DailyDashboardResponse
from services.portfolio_cockpit_service import get_today_view

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/daily-dashboard", response_model=DailyDashboardResponse)
def daily_dashboard():
    return get_today_view(include_freshness=True)
