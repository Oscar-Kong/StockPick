"""Structured API error payloads for portfolio and quant endpoints."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def new_request_id(prefix: str = "req") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def portfolio_error(
    *,
    code: str,
    message: str,
    status_code: int = 400,
    retryable: bool = False,
    request_id: str | None = None,
    log_detail: str | None = None,
) -> HTTPException:
    rid = request_id or new_request_id()
    if log_detail:
        logger.error("[%s] %s: %s", code, message, log_detail)
    return HTTPException(
        status_code=status_code,
        detail={
            "error": code,
            "message": message,
            "request_id": rid,
            "retryable": retryable,
        },
    )


def detail_message(detail: Any) -> str:
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error") or detail)
    if isinstance(detail, str):
        return detail
    return str(detail)
