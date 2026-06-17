"""Demo-mode guards and request validation for public deployments."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import HTTPException

from config import (
    DEMO_MAX_ANALYSIS_SYMBOLS,
    DEMO_MAX_BACKTEST_DAYS,
    DEMO_MAX_BACKTEST_SYMBOLS,
    DEMO_MAX_QUANT_JOB_SYMBOLS,
    DEMO_MAX_SCAN_SYMBOLS,
)
from utils.api_errors import new_request_id, portfolio_error


def _demo_mode() -> bool:
    import config

    return bool(config.DEMO_MODE)


def is_demo_mode() -> bool:
    return _demo_mode()


def demo_action_disabled(
    message: str = "This action is disabled in the public demo.",
    *,
    status_code: int = 403,
) -> HTTPException:
    return portfolio_error(
        code="DEMO_ACTION_DISABLED",
        message=message,
        status_code=status_code,
        retryable=False,
        request_id=new_request_id(),
    )


def require_non_demo_mode(
    message: str = "This action is disabled in the public demo.",
) -> None:
    if _demo_mode():
        raise demo_action_disabled(message)


def demo_limit_error(field: str, limit: int, actual: int) -> HTTPException:
    return portfolio_error(
        code="DEMO_LIMIT_EXCEEDED",
        message=f"Public demo limit: {field} cannot exceed {limit} (requested {actual}).",
        status_code=400,
        retryable=False,
        request_id=new_request_id(),
    )


def enforce_symbol_count(symbols: list[str], *, max_count: int, field: str = "symbols") -> list[str]:
    cleaned = [s.strip().upper() for s in symbols if s and s.strip()]
    if _demo_mode() and len(cleaned) > max_count:
        raise demo_limit_error(field, max_count, len(cleaned))
    return cleaned


def enforce_scan_options(options: Any | None) -> Any | None:
    if not _demo_mode():
        return options
    from models.schemas import ScanOptions

    import config

    base = options if options is not None else ScanOptions()
    cap = min(int(config.DEMO_MAX_SCAN_SYMBOLS), int(base.max_results)) if _demo_mode() else int(base.max_results)
    if _demo_mode() and cap < int(base.max_results):
        return base.model_copy(update={"max_results": cap})
    return base


def enforce_compare_symbols(parts: list[str]) -> list[str]:
    return enforce_symbol_count(parts, max_count=DEMO_MAX_ANALYSIS_SYMBOLS, field="analysis symbols")


def enforce_backtest_symbols(symbols: list[str]) -> list[str]:
    import config

    cap = config.DEMO_MAX_BACKTEST_SYMBOLS if _demo_mode() else len(symbols) or 10_000
    return enforce_symbol_count(symbols, max_count=cap, field="backtest symbols")


def enforce_backtest_date_range(start: str | date | None, end: str | date | None) -> None:
    if not _demo_mode() or not start or not end:
        return
    s = _to_date(start)
    e = _to_date(end)
    if s is None or e is None:
        return
    if (e - s).days > DEMO_MAX_BACKTEST_DAYS:
        raise demo_limit_error("backtest days", DEMO_MAX_BACKTEST_DAYS, (e - s).days)


def enforce_research_max_symbols(max_symbols: int | None) -> int:
    cap = DEMO_MAX_QUANT_JOB_SYMBOLS if _demo_mode() else 10_000
    value = int(max_symbols or cap)
    if _demo_mode() and value > cap:
        raise demo_limit_error("research symbols", cap, value)
    return value


def _to_date(value: str | date) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
