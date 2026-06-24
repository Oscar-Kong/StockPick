"""Structured skip reasons for Stage B scan observability."""
from __future__ import annotations

from typing import Any

MISSING_HISTORY = "missing_history"
STALE_HISTORY = "stale_history"
PROVIDER_FAILURE = "provider_failure"
INVALID_PRICE = "invalid_price"
MISSING_REQUIRED_FUNDAMENTALS = "missing_required_fundamentals"
CANDIDATE_BUILD_EXCEPTION = "candidate_build_exception"
STRICT_FILTER_REJECTION = "strict_filter_rejection"


def record_scan_skip(
    skipped: list[dict[str, Any]],
    *,
    symbol: str,
    reason: str,
    detail: str | None = None,
) -> None:
    """Append a structured skip record for scan metadata."""
    entry: dict[str, Any] = {"symbol": symbol.upper(), "reason": reason}
    if detail:
        entry["detail"] = detail
    skipped.append(entry)


def map_quality_exclusion_reason(exclude_reason: str, history_bars: int) -> str:
    """Map should_exclude_low_quality text to a structured skip reason."""
    lower = (exclude_reason or "").lower()
    if "insufficient history" in lower:
        return STALE_HISTORY if history_bars > 0 else MISSING_HISTORY
    if "data quality" in lower:
        return MISSING_REQUIRED_FUNDAMENTALS
    return STALE_HISTORY if history_bars > 0 else MISSING_HISTORY
