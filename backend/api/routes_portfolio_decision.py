"""Daily portfolio decision API."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from data.portfolio_store import get_latest_decision, list_decision_history
from models.schemas import (
    PortfolioDecisionHistoryItem,
    PortfolioDecisionResponse,
    PortfolioDecisionRunResponse,
)
from services.portfolio_decision_service import run_stored_portfolio_decision

router = APIRouter(prefix="/portfolio/daily-decision", tags=["portfolio-decision"])


@router.post("/run", response_model=PortfolioDecisionRunResponse)
def run_daily_decision():
    try:
        decision = run_stored_portfolio_decision(trigger="manual", persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Daily decision failed: {exc}") from exc

    latest = get_latest_decision()
    return PortfolioDecisionRunResponse(
        ok=True,
        trigger="manual",
        decision=decision,
        snapshot_id=latest["id"] if latest else None,
    )


@router.get("/latest", response_model=Optional[PortfolioDecisionResponse])
def latest_daily_decision():
    row = get_latest_decision()
    if not row:
        return None
    payload = row.get("payload") or {}
    return PortfolioDecisionResponse(**payload)


@router.get("/history", response_model=list[PortfolioDecisionHistoryItem])
def decision_history(limit: int = 30):
    return [PortfolioDecisionHistoryItem(**r) for r in list_decision_history(limit=min(limit, 100))]
