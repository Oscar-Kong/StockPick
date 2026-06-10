"""Brokerage CSV import and portfolio holdings."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import BrokerageCsvImportResponse, CurrentPortfolioResponse
from services.portfolio_snapshot_service import (
    DISCLAIMER,
    get_current_portfolio,
    import_robinhood_csv_and_decide,
    list_import_history,
)

router = APIRouter(prefix="/brokerage", tags=["brokerage"])


@router.post("/import/robinhood-csv", response_model=BrokerageCsvImportResponse)
async def import_robinhood_csv_route(
    file: UploadFile = File(...),
    cash: float | None = Form(None),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        result = import_robinhood_csv_and_decide(content, file.filename, cash=cash)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {exc}") from exc
    return BrokerageCsvImportResponse(**result)


@router.get("/imports")
def brokerage_imports():
    return {"imports": list_import_history()}


router_portfolio = APIRouter(prefix="/portfolio", tags=["portfolio-holdings"])


@router_portfolio.get("/current", response_model=CurrentPortfolioResponse)
def portfolio_current():
    data = get_current_portfolio()
    return CurrentPortfolioResponse(**data, disclaimer=DISCLAIMER)
