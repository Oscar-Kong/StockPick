"""Runtime API / feature toggle settings."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from models.schemas import ApiSettingsPatchRequest, ApiSettingsResetRequest, ApiSettingsResponse
from services.api_settings import list_api_settings, patch_api_settings, reset_api_settings
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
