"""Structured skip reasons for Stage B scan observability."""
from __future__ import annotations

from typing import Any

MISSING_HISTORY = "missing_history"
INSUFFICIENT_HISTORY = "insufficient_history"
STALE_HISTORY = "stale_history"
PROVIDER_FAILURE = "provider_failure"
INVALID_PRICE = "invalid_price"
MISSING_REQUIRED_FUNDAMENTALS = "missing_required_fundamentals"
CANDIDATE_BUILD_EXCEPTION = "candidate_build_exception"
STRICT_FILTER_REJECTION = "strict_filter_rejection"

# Scan-level fallback taxonomy (machine-readable).
FALLBACK_NONE = "none"
FALLBACK_PROVIDER_COVERAGE_INSUFFICIENT = "provider_coverage_insufficient"
FALLBACK_PROVIDER_UNAVAILABLE = "provider_unavailable"
FALLBACK_HISTORY_POLICY_MISMATCH = "history_policy_mismatch"
FALLBACK_STRICT_FILTERS_REJECTED_ALL = "strict_filters_rejected_all"
FALLBACK_INSUFFICIENT_VALID_CANDIDATES = "insufficient_valid_candidates"
FALLBACK_STALE_DATA = "stale_data_fallback"

PROVIDER_FALLBACK_REASONS = frozenset(
    {
        FALLBACK_PROVIDER_COVERAGE_INSUFFICIENT,
        FALLBACK_PROVIDER_UNAVAILABLE,
    }
)


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
        return INSUFFICIENT_HISTORY if history_bars > 0 else MISSING_HISTORY
    if "data quality" in lower:
        return MISSING_REQUIRED_FUNDAMENTALS
    return STALE_HISTORY if history_bars > 0 else MISSING_HISTORY


def classify_scan_fallback_reason(
    *,
    published_normal_pool: bool,
    partial_universe: bool,
    provider_requested: int,
    provider_received: int,
    skipped: list[dict[str, Any]],
    history_gate_exclusion_count: int,
    used_fallback_candidates: bool,
) -> str:
    """Classify why a scan published fallback rows (or none)."""
    if published_normal_pool and not used_fallback_candidates:
        return FALLBACK_NONE

    if not used_fallback_candidates:
        return FALLBACK_NONE

    if provider_requested > 0 and provider_received == 0:
        return FALLBACK_PROVIDER_UNAVAILABLE

    if partial_universe or (
        provider_requested > 0 and provider_received < provider_requested
    ):
        return FALLBACK_PROVIDER_COVERAGE_INSUFFICIENT

    reasons = [str(s.get("reason") or "") for s in skipped]
    details = " ".join(str(s.get("detail") or "") for s in skipped).lower()

    # Detect the pre-fix mismatch: frames rejected solely against global 252.
    if history_gate_exclusion_count > 0 and (
        "< 252" in details or "<252" in details or "252 bars" in details
    ):
        return FALLBACK_HISTORY_POLICY_MISMATCH

    stale_count = sum(1 for r in reasons if r == STALE_HISTORY)
    if reasons and stale_count >= max(1, (len(reasons) + 1) // 2):
        return FALLBACK_STALE_DATA

    strict_count = sum(1 for r in reasons if r == STRICT_FILTER_REJECTION)
    insuf_count = sum(1 for r in reasons if r in {INSUFFICIENT_HISTORY, MISSING_HISTORY})
    if reasons and (strict_count + insuf_count) >= max(1, (len(reasons) + 1) // 2):
        return FALLBACK_STRICT_FILTERS_REJECTED_ALL

    if history_gate_exclusion_count > 0:
        return FALLBACK_STRICT_FILTERS_REJECTED_ALL

    return FALLBACK_INSUFFICIENT_VALID_CANDIDATES


def is_provider_limited_fallback(fallback_reason: str) -> bool:
    return fallback_reason in PROVIDER_FALLBACK_REASONS
