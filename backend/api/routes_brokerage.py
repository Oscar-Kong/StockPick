"""Brokerage CSV import and portfolio holdings."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import BrokerageCsvImportResponse, CurrentPortfolioResponse
from utils.pydantic_util import model_to_dict
from services.portfolio_snapshot_service import (
    DISCLAIMER,
    get_current_portfolio,
    import_robinhood_csv_and_decide,
    list_import_history,
    validate_robinhood_csv,
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


@router.post("/validate/robinhood-csv")
async def validate_robinhood_csv_route(file: UploadFile = File(...)):
    """Dev validation: parse CSV and return reconstruction + debug without persisting."""
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        report = validate_robinhood_csv(content)
        from services.portfolio_decision_service import run_portfolio_daily_decision
        from models.schemas import Bucket, PortfolioDecisionRequest, PortfolioHolding

        holdings = [
            PortfolioHolding(
                symbol=h["symbol"],
                shares=h["shares"],
                avg_cost=h["avg_cost"],
                bucket=Bucket(h.get("bucket", "penny")),
            )
            for h in report.get("open_holdings") or []
        ]
        cash = max(0.0, float(report.get("cash_impact") or 0))
        if holdings:
            try:
                decision = run_portfolio_daily_decision(
                    PortfolioDecisionRequest(cash=cash, holdings=holdings, persist=False)
                )
                report["generated_decision"] = model_to_dict(decision)
            except Exception as exc:
                report["decision_error"] = str(exc)
        return report
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Validation failed: {exc}") from exc


router_portfolio = APIRouter(prefix="/portfolio", tags=["portfolio-holdings"])


@router_portfolio.get("/current", response_model=CurrentPortfolioResponse)
def portfolio_current():
    data = get_current_portfolio()
    return CurrentPortfolioResponse(**data, disclaimer=DISCLAIMER)
