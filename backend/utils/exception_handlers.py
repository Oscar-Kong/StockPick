"""Production-safe exception handling."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from config import APP_ENV, DEMO_MODE
from utils.api_errors import new_request_id

logger = logging.getLogger(__name__)


def _safe_message(exc: Exception) -> str:
    if APP_ENV == "development" and not DEMO_MODE:
        return str(exc) or "Request failed"
    return "An unexpected error occurred. Please try again later."


def register_exception_handlers(app) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        rid = new_request_id()
        detail = exc.detail
        if isinstance(detail, dict):
            payload = dict(detail)
            payload.setdefault("request_id", rid)
            return JSONResponse(status_code=exc.status_code, content={"detail": payload})
        if APP_ENV == "production" or DEMO_MODE:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "detail": {
                        "error": "HTTP_ERROR",
                        "message": str(detail),
                        "request_id": rid,
                        "retryable": exc.status_code >= 500,
                    }
                },
            )
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        rid = new_request_id()
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid request parameters.",
                    "request_id": rid,
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        rid = new_request_id()
        logger.exception("[%s] Unhandled error on %s", rid, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": {
                    "error": "INTERNAL_ERROR",
                    "message": _safe_message(exc),
                    "request_id": rid,
                    "retryable": True,
                }
            },
        )
