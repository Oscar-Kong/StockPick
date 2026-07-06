"""Daily trading plan review persistence API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from data.portfolio_store import get_daily_trading_plan_review, upsert_daily_trading_plan_review
from models.schemas import DailyTradingPlanReviewRequest, DailyTradingPlanReviewResponse
from utils.demo_guard import require_non_demo_mode

router = APIRouter(prefix="/portfolio/daily-trading-plan", tags=["daily-trading-plan"])


@router.get("/review", response_model=Optional[DailyTradingPlanReviewResponse])
def get_review(trading_date: str):
    row = get_daily_trading_plan_review(trading_date)
    if not row:
        return None
    return DailyTradingPlanReviewResponse(**row)


@router.post("/review", response_model=DailyTradingPlanReviewResponse)
def save_review(body: DailyTradingPlanReviewRequest):
    require_non_demo_mode()
    try:
        row = upsert_daily_trading_plan_review(
            trading_date=body.trading_date,
            plan_id=body.plan_id,
            planned_decision=body.planned_decision,
            primary_candidate=body.primary_candidate,
            plan_followed=body.plan_followed,
            actual_action=body.actual_action,
            overridden_rules=body.overridden_rules,
            user_notes=body.user_notes,
            end_of_day_outcome=body.end_of_day_outcome,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save review: {exc}") from exc
    return DailyTradingPlanReviewResponse(**row)
