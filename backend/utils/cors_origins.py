"""Parse and validate CORS allowed origins."""
from __future__ import annotations

import re

from config import ALLOWED_ORIGINS, APP_ENV, DEMO_MODE

_VERCEL_PREVIEW = re.compile(
    r"^https://[a-z0-9][a-z0-9-]*-[a-z0-9][a-z0-9-]*-oscar-kongs-projects\.vercel\.app$",
    re.IGNORECASE,
)


def origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    if APP_ENV != "production" and not DEMO_MODE:
        return origin in ALLOWED_ORIGINS
    return False


def get_cors_allow_origins() -> list[str]:
    """Origins passed to CORSMiddleware (exact match list)."""
    return list(ALLOWED_ORIGINS)


def validate_origin_config() -> None:
    if APP_ENV == "production" and not ALLOWED_ORIGINS:
        import logging

        logging.warning(
            "ALLOWED_ORIGINS is empty in production — browser clients cannot call the API until set."
        )
