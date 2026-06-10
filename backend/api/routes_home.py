"""Home dashboard — daily decision first."""
from __future__ import annotations

from fastapi import APIRouter

from models.schemas import DailyDashboardResponse
from services.home_dashboard_service import build_daily_dashboard

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/daily-dashboard", response_model=DailyDashboardResponse)
def daily_dashboard():
    return build_daily_dashboard()
