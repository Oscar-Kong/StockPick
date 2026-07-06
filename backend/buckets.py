"""Active investment sleeves (buckets)."""
from __future__ import annotations

from core.sleeve import normalize_sleeve

ACTIVE_BUCKETS: tuple[str, ...] = ("penny", "compounder")
DEFAULT_BUCKET = "penny"


def is_active_bucket(bucket: str | None) -> bool:
    return (bucket or "").lower() in ACTIVE_BUCKETS


def resolve_bucket(bucket: str | None, *, allow_deprecated: bool = True) -> str:
    """Return a valid active bucket; legacy ``medium`` maps to penny via normalize_sleeve."""
    del allow_deprecated
    return normalize_sleeve(bucket, default=DEFAULT_BUCKET)


def parse_bucket_query(raw: str | None, *, default: str = DEFAULT_BUCKET) -> str:
    """Normalize API query/path bucket strings (legacy ``medium`` → penny)."""
    return normalize_sleeve(raw, default=default)
