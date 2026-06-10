"""Active vs deprecated investment sleeves (buckets)."""
from __future__ import annotations

ACTIVE_BUCKETS: tuple[str, ...] = ("penny", "compounder")
DEPRECATED_BUCKETS: tuple[str, ...] = ("medium",)
DEFAULT_BUCKET = "penny"
ALL_BUCKETS: tuple[str, ...] = ACTIVE_BUCKETS + DEPRECATED_BUCKETS


def is_active_bucket(bucket: str | None) -> bool:
    return (bucket or "").lower() in ACTIVE_BUCKETS


def is_deprecated_bucket(bucket: str | None) -> bool:
    return (bucket or "").lower() in DEPRECATED_BUCKETS


def resolve_bucket(bucket: str | None, *, allow_deprecated: bool = True) -> str:
    """Return a valid bucket string; unknown values fall back to DEFAULT_BUCKET."""
    val = (bucket or "").lower()
    if val in ALL_BUCKETS:
        if not allow_deprecated and val in DEPRECATED_BUCKETS:
            return DEFAULT_BUCKET
        return val
    return DEFAULT_BUCKET
