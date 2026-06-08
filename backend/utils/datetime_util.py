"""UTC datetime helpers — always serialize API timestamps with Z suffix."""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_iso_z(dt: datetime | None) -> str | None:
    """Naive UTC → ISO-8601 with Z (for JSON APIs)."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    text = dt.isoformat()
    if text.endswith("Z") or "+" in text[-7:] or (len(text) > 6 and text[-6] in "+-"):
        return text
    return f"{text}Z"


def parse_api_datetime(value: str | None) -> datetime | None:
    """Parse client ISO string; normalize to naive UTC for storage."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
