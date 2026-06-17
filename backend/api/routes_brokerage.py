"""Brokerage CSV import and portfolio holdings."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import BrokerageCsvImportResponse, CurrentPortfolioResponse
from utils.demo_guard import require_non_demo_mode
from utils.pydantic_util import model_to_dict
from services.portfolio_snapshot_service import (
    get_current_portfolio,
    import_robinhood_csv_and_decide,
    list_import_history,
    set_buying_power,
    validate_robinhood_csv,
)

router = APIRouter(prefix="/brokerage", tags=["brokerage"])


@router.post("/import/robinhood-csv", response_model=BrokerageCsvImportResponse)
async def import_robinhood_csv_route(
    file: UploadFile = File(...),
    cash: float | None = Form(None),
    replace: bool = Form(False),
):
    require_non_demo_mode()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        result = import_robinhood_csv_and_decide(content, file.filename, cash=cash, replace=replace)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV import failed: {exc}") from exc
    return BrokerageCsvImportResponse(**result)


@router.post("/buying-power")
def update_buying_power(
    cash: float = Form(..., ge=0),
    reserved_cash: float = Form(0, ge=0),
    ipo_shares: float | None = Form(None, ge=0),
    ipo_list_price: float | None = Form(None, ge=0),
):
    """Set Robinhood buying power and optional reserved cash (e.g. upcoming IPO)."""
    require_non_demo_mode()
    try:
        from services.portfolio_decision_service import run_stored_portfolio_decision
        from services.portfolio_snapshot_service import set_portfolio_cash

        result = set_portfolio_cash(
            buying_power=cash,
            reserved_cash=reserved_cash,
            ipo_shares=ipo_shares,
            ipo_list_price=ipo_list_price,
        )
        try:
            decision = run_stored_portfolio_decision(trigger="buying_power", persist=True)
            result["decision"] = model_to_dict(decision)
        except Exception as exc:
            result["decision_error"] = str(exc)[:200]
        return result
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/imports")
def brokerage_imports():
    return {"imports": list_import_history()}


@router.post("/validate/robinhood-csv")
async def validate_robinhood_csv_route(file: UploadFile = File(...)):
    """Dev validation: parse CSV and return reconstruction + debug without persisting."""
    require_non_demo_mode()
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
    return CurrentPortfolioResponse(**data)
