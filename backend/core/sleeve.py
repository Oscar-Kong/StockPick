"""Active product sleeves and legacy compatibility normalization."""
from __future__ import annotations

from models.schemas import Bucket

ACTIVE_SLEEVES = frozenset({"penny", "compounder"})
LEGACY_SLEEVE_ALIASES = {"medium": "penny"}


def normalize_sleeve(sleeve: str | None, *, default: str = "penny") -> str:
    """Map deprecated medium requests to penny; default unknown values to penny."""
    if not sleeve:
        return default
    val = str(sleeve).strip().lower()
    if val in LEGACY_SLEEVE_ALIASES:
        return LEGACY_SLEEVE_ALIASES[val]
    if val in ACTIVE_SLEEVES:
        return val
    return default


def normalize_bucket(bucket: Bucket | str | None, *, default: Bucket = Bucket.penny) -> Bucket:
    if bucket is None:
        return default
    raw = bucket.value if isinstance(bucket, Bucket) else str(bucket)
    normalized = normalize_sleeve(raw, default=default.value)
    return Bucket(normalized)
