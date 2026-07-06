"""Runtime API / feature toggle settings."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from config import DEMO_MODE, SCAN_EMAIL_TO
from models.schemas import (
    ApiSettingsPatchRequest,
    ApiSettingsResetRequest,
    ApiSettingsResponse,
    MailingListAddRequest,
    MailingListImportEnvResponse,
    MailingListPatchRequest,
    MailingListResponse,
    MailingListSubscriberItem,
)
from services.api_settings import list_api_settings, patch_api_settings, reset_api_settings
from services.mailing_list_store import get_mailing_list_store, get_mailing_list_summary
from services.scan_email_config import parse_recipients
from utils.demo_guard import require_non_demo_mode

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/apis", response_model=ApiSettingsResponse)
def get_api_settings():
    return ApiSettingsResponse(**list_api_settings())


@router.patch("/apis", response_model=ApiSettingsResponse)
def update_api_settings(body: ApiSettingsPatchRequest):
    require_non_demo_mode()
    try:
        data = patch_api_settings(body.updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiSettingsResponse(**data)


@router.post("/apis/reset", response_model=ApiSettingsResponse)
def reset_settings(body: ApiSettingsResetRequest | None = None):
    require_non_demo_mode()
    keys = body.keys if body else None
    try:
        data = reset_api_settings(keys)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiSettingsResponse(**data)


def _mailing_list_response() -> MailingListResponse:
    summary = get_mailing_list_summary()
    return MailingListResponse(
        subscribers=[MailingListSubscriberItem(**item) for item in summary["subscribers"]],
        active_count=summary["active_count"],
        recipient_source=summary["recipient_source"],
        recipient_count=summary["recipient_count"],
        read_only=DEMO_MODE,
    )


@router.get("/mailing-list", response_model=MailingListResponse)
def get_mailing_list():
    return _mailing_list_response()


@router.post("/mailing-list", response_model=MailingListResponse)
def add_mailing_list_subscriber(body: MailingListAddRequest):
    require_non_demo_mode()
    store = get_mailing_list_store()
    try:
        store.add_subscriber(body.email, label=body.label)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _mailing_list_response()


@router.patch("/mailing-list/{subscriber_id}", response_model=MailingListResponse)
def patch_mailing_list_subscriber(subscriber_id: str, body: MailingListPatchRequest):
    require_non_demo_mode()
    store = get_mailing_list_store()
    try:
        store.update_subscriber(
            subscriber_id,
            enabled=body.enabled,
            label=body.label,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _mailing_list_response()


@router.delete("/mailing-list/{subscriber_id}", response_model=MailingListResponse)
def remove_mailing_list_subscriber(subscriber_id: str):
    require_non_demo_mode()
    store = get_mailing_list_store()
    try:
        store.remove_subscriber(subscriber_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _mailing_list_response()


@router.post("/mailing-list/import-env", response_model=MailingListImportEnvResponse)
def import_mailing_list_from_env():
    require_non_demo_mode()
    store = get_mailing_list_store()
    env_emails = parse_recipients(SCAN_EMAIL_TO)
    if not env_emails:
        raise HTTPException(status_code=400, detail="SCAN_EMAIL_TO is empty in .env")
    try:
        imported = store.import_from_env(env_emails)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    summary = get_mailing_list_summary()
    return MailingListImportEnvResponse(
        imported=imported,
        subscribers=[MailingListSubscriberItem(**item) for item in summary["subscribers"]],
        active_count=summary["active_count"],
        recipient_source=summary["recipient_source"],
        recipient_count=summary["recipient_count"],
    )
