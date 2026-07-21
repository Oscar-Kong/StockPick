"""Brokerage CSV import and portfolio holdings."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from models.schemas import (
    BrokerageCsvImportResponse,
    CsvApproveRequest,
    CsvPreviewResponse,
    CurrentPortfolioResponse,
    LedgerEntryCreate,
    LedgerEntryResponse,
    LedgerEntryUpdate,
    LedgerListResponse,
)
from utils.demo_guard import require_non_demo_mode
from utils.pydantic_util import model_to_dict
from services.portfolio_ledger_service import (
    approve_csv_import,
    create_ledger_entry,
    list_ledger_api,
    preview_robinhood_csv,
    rebuild_ledger_holdings,
    remove_ledger_entry,
    update_ledger_entry,
)
from services.portfolio_snapshot_service import (
    get_current_portfolio,
    import_robinhood_csv_and_decide,
    list_import_history,
    robinhood_mcp_status,
    set_buying_power,
    validate_robinhood_csv,
)

router = APIRouter(prefix="/brokerage", tags=["brokerage"])


@router.get("/ledger", response_model=LedgerListResponse)
def get_portfolio_ledger():
    """All buy/sell/cash ledger rows that drive portfolio holdings."""
    require_non_demo_mode()
    return LedgerListResponse(**list_ledger_api())


@router.post("/ledger", response_model=LedgerEntryResponse)
def post_ledger_entry(body: LedgerEntryCreate):
    require_non_demo_mode()
    try:
        return LedgerEntryResponse(**create_ledger_entry(body.model_dump()))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/ledger/{row_id}", response_model=LedgerEntryResponse)
def patch_ledger_entry(row_id: int, body: LedgerEntryUpdate):
    require_non_demo_mode()
    try:
        return LedgerEntryResponse(**update_ledger_entry(row_id, body.model_dump(exclude_unset=True)))
    except ValueError as exc:
        msg = str(exc)
        if "locked" in msg.lower():
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=404, detail=msg) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/ledger/{row_id}")
def delete_ledger_entry_route(row_id: int):
    require_non_demo_mode()
    try:
        remove_ledger_entry(row_id)
        return {"deleted": True, "id": row_id}
    except ValueError as exc:
        msg = str(exc)
        if "locked" in msg.lower():
            raise HTTPException(status_code=409, detail=msg) from exc
        raise HTTPException(status_code=404, detail=msg) from exc


@router.post("/ledger/rebuild")
def rebuild_ledger_route():
    require_non_demo_mode()
    try:
        return rebuild_ledger_holdings()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/preview/robinhood-csv", response_model=CsvPreviewResponse)
async def preview_robinhood_csv_route(
    file: UploadFile = File(...),
    replace: bool = Form(False),
):
    """Parse CSV and return editable rows + projected holdings — nothing persisted."""
    require_non_demo_mode()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a .csv file")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return CsvPreviewResponse(**preview_robinhood_csv(content, file.filename, replace=replace))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV preview failed: {exc}") from exc


@router.post("/import/robinhood-csv/approve", response_model=BrokerageCsvImportResponse)
def approve_robinhood_csv_route(body: CsvApproveRequest):
    """Persist user-reviewed CSV rows after manual validation."""
    require_non_demo_mode()
    try:
        result = approve_csv_import(
            filename=body.filename,
            rows=[r.model_dump() for r in body.rows],
            replace=body.replace,
            cash=body.cash,
        )
        return BrokerageCsvImportResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"CSV approve failed: {exc}") from exc


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


@router.get("/robinhood-mcp/status")
def robinhood_mcp_status_route(
    probe: bool = Query(False, description="Run a live MCP connectivity probe (accounts/portfolio/positions)"),
):
    """Robinhood MCP OAuth status; optional live connectivity probe."""
    return robinhood_mcp_status(probe=probe)


@router.post("/robinhood-mcp/test")
def robinhood_mcp_test_route():
    """Live connectivity test against Robinhood MCP (no full ledger sync)."""
    return robinhood_mcp_status(probe=True)


@router.post("/sync/robinhood-mcp")
def sync_robinhood_mcp_route(
    run_decision: bool = Query(False, description="Run daily decision after sync (slower)"),
):
    """Start background Robinhood MCP sync (positions + order history)."""
    require_non_demo_mode()
    from integrations.robinhood.mcp_client import RobinhoodMcpClient
    from services.robinhood_mcp_sync_service import start_robinhood_mcp_sync

    client = RobinhoodMcpClient()
    if not client.is_configured():
        raise HTTPException(
            status_code=401,
            detail="Robinhood MCP not authenticated. Run: ./scripts/robinhood-mcp-login.sh",
        )
    job_id = start_robinhood_mcp_sync(run_decision=run_decision)
    return {"job_id": job_id, "status": "running", "message": "Robinhood sync started"}


@router.get("/sync/robinhood-mcp/{job_id}")
def sync_robinhood_mcp_job_route(job_id: str):
    """Poll Robinhood MCP sync job status."""
    from services.robinhood_mcp_sync_service import get_robinhood_mcp_sync_job

    job = get_robinhood_mcp_sync_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return job


router_portfolio = APIRouter(prefix="/portfolio", tags=["portfolio-holdings"])


@router_portfolio.get("/current", response_model=CurrentPortfolioResponse)
def portfolio_current():
    data = get_current_portfolio()
    return CurrentPortfolioResponse(**data)
