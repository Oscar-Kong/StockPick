"""Deterministic canonical session calendar hashing."""
from __future__ import annotations

import hashlib
import json

from engines.factor.discovery.sessions import CanonicalSessionCalendar

CALENDAR_POLICY_ID = "panel_union_v1"
CALENDAR_VERSION = "factor-sessions-v1"


def canonical_session_hash(calendar: CanonicalSessionCalendar) -> str:
    """Hash ordered sessions, serialization convention, and calendar policy metadata."""
    payload = {
        "calendar_id": calendar.calendar_id,
        "calendar_policy_id": CALENDAR_POLICY_ID,
        "calendar_version": calendar.version,
        "session_serialization": "YYYY-MM-DD",
        "sessions": calendar.to_hash_payload(),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
