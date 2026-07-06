"""Ops API routes for morning scan email notifications."""
from __future__ import annotations

from fastapi import APIRouter

from models.schemas import (
    MorningScanEmailHistoryResponse,
    MorningScanEmailSendRequest,
    MorningScanEmailSendResponse,
    MorningScanEmailStatusResponse,
)
from services.morning_scan_email_service import (
    get_morning_scan_email_history,
    get_morning_scan_email_status,
    run_morning_scan_email,
)
from utils.demo_guard import require_non_demo_mode

router = APIRouter(prefix="/ops/notifications/morning-scan", tags=["ops"])


@router.post("/send", response_model=MorningScanEmailSendResponse)
async def send_morning_scan_email(body: MorningScanEmailSendRequest):
    require_non_demo_mode("Morning scan email is disabled in the public demo.")
    result = await run_morning_scan_email(
        force=body.force,
        dry_run=body.dry_run,
        source="ops_api",
    )
    return MorningScanEmailSendResponse(
        status=result.status,
        message=result.message,
        delivery_id=result.delivery_id,
        dry_run=result.dry_run,
        subject=result.subject,
        html_preview=result.html_preview,
        text_preview=result.text_preview,
        recipients=list(result.recipients),
    )


@router.get("/status", response_model=MorningScanEmailStatusResponse)
def morning_scan_email_status():
    return MorningScanEmailStatusResponse(**get_morning_scan_email_status())


@router.get("/history", response_model=MorningScanEmailHistoryResponse)
def morning_scan_email_history(limit: int = 20):
    return MorningScanEmailHistoryResponse(items=get_morning_scan_email_history(limit=limit))
