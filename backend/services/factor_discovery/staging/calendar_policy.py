"""Canonical trading calendar policy for staging."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

CALENDAR_ID = "us_equity_observed_union_v1"
CALENDAR_VERSION = "2026-03-01"
FALLBACK_CALENDAR_ID = "observed_panel_union_v1"


def is_weekend(date_str: str) -> bool:
    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
    return dt.weekday() >= 5


def calendar_session_hash(sessions: list[str]) -> str:
    canonical = json.dumps(sorted(sessions), separators=(",", ":"))
    return f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"


def audit_calendar(sessions: list[str]) -> dict:
    weekend_sessions = [d for d in sessions if is_weekend(d)]
    gaps: list[str] = []
    ordered = sorted(sessions)
    for i in range(1, len(ordered)):
        prev = datetime.strptime(ordered[i - 1], "%Y-%m-%d")
        cur = datetime.strptime(ordered[i], "%Y-%m-%d")
        if (cur - prev).days > 7:
            gaps.append(f"{ordered[i-1]}->{ordered[i]}")
    return {
        "calendar_id": CALENDAR_ID,
        "calendar_version": CALENDAR_VERSION,
        "fallback_calendar_id": FALLBACK_CALENDAR_ID,
        "session_count": len(sessions),
        "earliest_session": ordered[0] if ordered else None,
        "latest_session": ordered[-1] if ordered else None,
        "weekend_sessions": weekend_sessions,
        "large_gap_count": len(gaps),
        "session_hash": calendar_session_hash(sessions) if sessions else None,
        "limitations": [
            "Observed union calendar used when exchange holiday table unavailable",
            "Weekend sessions flagged as diagnostic only",
        ],
    }
