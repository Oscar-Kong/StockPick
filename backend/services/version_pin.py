"""Pinned model versions for API responses and strict client checks."""
from __future__ import annotations

from fastapi import HTTPException

from config import (
    APP_ENV,
    FACTOR_MODEL_VERSION,
    MODEL_VERSION_STRICT,
    STRATEGY_VERSION,
)
from data.db_engine import database_dialect, is_postgres
from engines.jobs.queue import effective_backend, redis_available


def pinned_versions() -> dict:
    return {
        "strategy_version": STRATEGY_VERSION,
        "factor_model_version": FACTOR_MODEL_VERSION,
        "app_env": APP_ENV,
        "database_dialect": database_dialect(),
        "postgres": is_postgres(),
        "job_queue_backend": effective_backend(),
        "redis_connected": redis_available(),
        "model_version_strict": MODEL_VERSION_STRICT,
    }


def enforce_client_versions(
    *,
    strategy_version: str | None = None,
    factor_model_version: str | None = None,
) -> None:
    if not MODEL_VERSION_STRICT:
        return
    if strategy_version and strategy_version != STRATEGY_VERSION:
        raise HTTPException(
            status_code=409,
            detail=f"strategy_version mismatch: expected {STRATEGY_VERSION}",
        )
    if factor_model_version and factor_model_version != FACTOR_MODEL_VERSION:
        raise HTTPException(
            status_code=409,
            detail=f"factor_model_version mismatch: expected {FACTOR_MODEL_VERSION}",
        )
